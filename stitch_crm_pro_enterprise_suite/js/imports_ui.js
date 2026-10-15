import {apiPost} from './api.js';
import {modal,esc,field,table,downloadText,toast} from './ui.js';
const fields={companies:['name','industry','website','email','phone','address','city','state','country','size','revenue','description'],contacts:['first_name','last_name','email','phone','job_title','company_id','company_name','description'],leads:['title','company_id','company_name','contact_id','source','status','estimated_value','lead_score','description']};
function headerRow(text){let result=[],value='',quoted=false;for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quoted&&text[i+1]==='"'){value+='"';i++;}else quoted=!quoted;}else if(c===','&&!quoted){result.push(value.trim());value='';}else if((c==='\n'||c==='\r')&&!quoted){result.push(value.trim());return result;}else value+=c;}result.push(value.trim());return result;}
function errorCSV(errors){const cell=x=>{let value=String(x??'');if(/^[=+\-@\t\r\n]/.test(value))value="'"+value;return '"'+value.replaceAll('"','""')+'"';};return 'row,error\r\n'+errors.map(e=>[e.row,e.error].map(cell).join(',')).join('\r\n');}
export function openImport(entity,after){
  let text='',preview=null,signature='',complete=false;
  const dialog=modal({id:'import-modal',title:'Import '+entity,save:'Preview import',body:`<div class="field full"><label for="csv-file">CSV file</label><input id="csv-file" type="file" accept=".csv,text/csv" required/><small>UTF-8 CSV, up to 2 MB and 1,000 rows. Contact imports require email and an existing company ID or exact company name.</small></div>${field('mode','Duplicate records','select','skip',{choices:[['skip','Skip matching records'],['update','Update matching records using mapped columns']]})}<div id="import-mapping" class="field full"></div><div id="import-preview" class="field full"></div>`,onSave:async values=>{
    if(complete)return;
    if(!text)throw new Error('Choose a CSV file.');
    const mapping={};for(const [key,value] of Object.entries(values))if(key.startsWith('map_')&&value)mapping[key.slice(4)]=value;
    if(!Object.keys(mapping).length)throw new Error('Map at least one column.');
    const data={csv_text:text,mapping,mode:values.mode};const current=JSON.stringify(data);
    if(!preview||signature!==current){
      preview=await apiPost(`/imports/${entity}/preview`,data);signature=current;
      dialog.querySelector('#import-preview').innerHTML=`<h3>Preview</h3><p class="subtle">${preview.valid} valid · ${preview.duplicates} duplicates · ${preview.invalid} invalid. No records have been saved.</p><div class="import-preview">${table(['CSV row','Status','Mapped data or errors'],preview.rows.map(r=>`<tr><td>${r.row}</td><td>${esc(r.status)}</td><td>${esc(r.errors.length?r.errors.join('; '):JSON.stringify(r.data))}</td></tr>`))}</div>`;
      dialog.dataset.saveLabel='Import valid rows';return false;
    }
    const result=await apiPost(`/imports/${entity}/commit`,data);complete=true;
    dialog.querySelector('.fields').innerHTML=`<div class="field full"><p class="success" role="status">${result.created} created · ${result.updated} updated · ${result.skipped} skipped · ${result.failed} failed.</p>${result.errors.length?'<button type="button" id="import-errors">Download row errors</button>':''}</div>`;
    dialog.querySelector('#import-errors')?.addEventListener('click',()=>downloadText(errorCSV(result.errors),'import-errors.csv'));
    dialog.dataset.saveLabel='Close';toast('Import finished.');await after();return false;
  }});
  dialog.querySelector('#csv-file').onchange=async e=>{const file=e.target.files[0];preview=null;if(!file)return;if(file.size>2*1024*1024){text='';dialog.querySelector('#import-preview').textContent='Choose a CSV file up to 2 MB.';return;}text=(await file.text()).replace(/^\uFEFF/,'');const headers=headerRow(text);dialog.querySelector('#import-mapping').innerHTML='<h3>Map columns</h3><div class="fields">'+fields[entity].map(key=>field('map_'+key,key.replaceAll('_',' '),'select',headers.find(h=>h.toLowerCase().replaceAll(' ','_')===key)||'',{choices:[['','Do not import'],...headers.map(h=>[h,h])]})).join('')+'</div>';dialog.dataset.saveLabel='Preview import';dialog.querySelector('[type=submit]').textContent='Preview import';};
}
