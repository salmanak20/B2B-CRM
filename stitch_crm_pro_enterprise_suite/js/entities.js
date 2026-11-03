import {apiGet,apiPost,apiPut,apiDelete} from './api.js';
import {initApp,workspace} from './app.js';
import {getCurrentUser} from './auth.js';
import {canCreateOrEdit,canDelete,isManagerOrAdmin} from './rbac.js';
import {esc,heading,button,field,modal,table,empty,showError,toast,money,badge,date,downloadText} from './ui.js';
import {openImport} from './imports_ui.js';
const statuses=['new','contacted','qualified','nurturing','converted','unqualified','lost'];
const sources=['website','referral','email','phone','social_media','advertisement','cold_call','event','other'];
export const configs={
 companies:{title:'Companies',single:'Company',key:'name',columns:[['Company Name',r=>link('companies',r.id,r.name)],['Industry',r=>esc(r.industry||'—')],['Website',r=>esc(r.website||'—')],['Phone',r=>esc(r.phone||'—')],['Owner',r=>esc(r.owner?.name||'—')]],sorts:['name','created_at','industry'],fields:[['name','Company Name','text',true],['industry','Industry'],['website','Website','url'],['email','Email','email'],['phone','Phone','tel'],['address','Address'],['city','City'],['state','State'],['country','Country'],['size','Company Size'],['revenue','Annual Revenue (USD)','number'],['description','Description','textarea']]},
 contacts:{title:'Contacts',single:'Contact',key:'name',columns:[['Name',r=>link('contacts',r.id,r.name)],['Email',r=>esc(r.email||'—')],['Phone',r=>esc(r.phone||'—')],['Job Title',r=>esc(r.job_title||'—')],['Company',r=>r.company?link('companies',r.company.id,r.company.name):'—']],sorts:['name','created_at','email'],fields:[['first_name','First Name','text',true],['last_name','Last Name'],['email','Email','email'],['phone','Phone','tel'],['job_title','Job Title'],['company_id','Company','companies',true],['description','Notes','textarea']]},
 leads:{title:'Leads',single:'Lead',key:'title',columns:[['Lead',r=>link('leads',r.id,r.title)],['Contact',r=>esc(r.contact?.name||'—')],['Company',r=>esc(r.company?.name||'—')],['Source',r=>esc(r.source||'—')],['Status',r=>badge(r.status)],['Value',r=>money(r.estimated_value)]],sorts:['title','created_at','estimated_value','status'],filter:statuses,fields:[['title','Lead Title','text',true],['status','Status','status',true],['source','Source','source'],['estimated_value','Estimated Value (USD)','number'],['lead_score','Lead Score','number'],['company_id','Company','companies'],['contact_id','Contact','contacts'],['description','Description','textarea']]},
 tasks:{title:'Tasks',single:'Task',key:'title',columns:[['Task',r=>link('tasks',r.id,r.title)],['Due',r=>date(r.due_date)],['Priority',r=>badge(r.priority)],['Status',r=>badge(r.status)],['Assignee',r=>esc(r.assigned_to?.name||'Unassigned')]],filter:['pending','in_progress','completed','cancelled'],fields:[['title','Task Title','text',true],['description','Description','textarea'],['priority','Priority','priority',true],['status','Status','taskstatus',true],['due_date','Due Date','datetime-local'],['assigned_to_id','Assign To','users'],['company_id','Company','companies'],['contact_id','Contact','contacts'],['lead_id','Lead','leads'],['deal_id','Deal','deals']]},
 deals:{title:'Deals',single:'Deal',key:'title',columns:[['Deal',r=>link('deals',r.id,r.title)],['Value',r=>money(r.value)],['Status',r=>badge(r.status)],['Company',r=>esc(r.company?.name||'—')]],fields:[['title','Deal Title','text',true],['value','Deal Value (USD)','number',true],['probability','Probability (%)','number'],['expected_close_date','Expected Close Date','date'],['company_id','Company','companies'],['contact_id','Contact','contacts'],['lead_id','Lead','leads'],['description','Description','textarea']]}
};
export const link=(entity,id,label)=>`<a class="cell-title" href="/${entity}?id=${Number(id)}">${esc(label)}</a>`;
const enumChoices={status:statuses,source:sources,priority:['low','medium','high','urgent'],taskstatus:['pending','in_progress','completed','cancelled']};
export async function choices(type,selected){
  if(type==='users'){const users=await apiGet('/directory');return [['','Unassigned'],...users.map(u=>[u.id,u.name])];}
  const data=await apiGet('/'+type,{page_size:100});let records=data.items||data;
  if(selected&&!records.some(r=>String(r.id)===String(selected))){try{records=[await apiGet('/'+type+'/'+selected),...records];}catch{}}
  return [['','Select…'],...records.map(r=>[r.id,r.name||r.title])];
}
export function bindRemoteSearch(dialog){
  dialog.querySelectorAll('[data-lookup]').forEach(input=>{let timer,seq=0;input.oninput=()=>{clearTimeout(timer);const current=++seq;timer=setTimeout(async()=>{const select=dialog.querySelector('#'+input.dataset.select);try{const response=await apiGet('/'+input.dataset.lookup,{search:input.value,page_size:100});if(current!==seq)return;const old=select.selectedOptions[0];const values=response.items||response;const extra=old?.value&&!values.some(r=>String(r.id)===old.value)?[[old.value,old.textContent]]:[];select.innerHTML=[['','Select…'],...extra,...values.map(r=>[r.id,r.name||r.title])].map(([id,name])=>`<option value="${esc(id)}"${old?.value===String(id)?' selected':''}>${esc(name)}</option>`).join('');}catch(error){showError(dialog.querySelector('[data-form-error]'),error);}},250);};});
}
export async function recordForm(entity,record={},after=()=>{},extra={}){
  const c=configs[entity];const defs=[...c.fields];if(isManagerOrAdmin())defs.push(['owner_id','Owner','users']);
  let body='';
  if(entity==='deals'){
    const pipelines=await apiGet('/pipelines',{page_size:100});const pipeline=record.pipeline_id||extra.pipeline_id||pipelines.items[0]?.id;
    if(!pipeline)throw new Error('Create a pipeline and stages before creating a deal.');
    const board=await apiGet(`/pipelines/${pipeline}/board`);
    body+=field('pipeline_id','Pipeline','select',pipeline,{required:true,choices:pipelines.items.map(p=>[p.id,p.name])});
    body+=field('stage_id','Stage','select',record.stage_id||'',{required:true,id:'deal-stage-id',choices:[['','Select stage…'],...board.stages.map(s=>[s.id,s.name])]});
  }
  for(const [name,label,type='text',required=false] of defs){
    const id=`${c.single.toLowerCase()}-${name.replaceAll('_','-')}`;let value=record[name]??(name==='status'?(entity==='tasks'?'pending':'new'):name==='priority'?'medium':name==='owner_id'?getCurrentUser().id:'');
    if(type==='datetime-local'&&value){const parsed=new Date(value.endsWith('Z')?value:value+'Z');value=new Date(parsed.valueOf()-parsed.getTimezoneOffset()*60000).toISOString().slice(0,16);}
    if(enumChoices[type])body+=field(name,label,'select',value,{id,required,choices:(required?[]:[['','Not specified']]).concat(enumChoices[type].map(v=>[v,v.replaceAll('_',' ')]))});
    else if(['companies','contacts','leads','deals','users'].includes(type)){
      body+=field(name,label,'select',value,{id,required,choices:await choices(type,value)});
      if(type!=='users')body+=`<div class="field"><label for="${id}-search">Find ${esc(label.toLowerCase())}</label><input type="search" id="${id}-search" data-lookup="${type}" data-select="${id}" placeholder="Search stored records…"/></div>`;
    }else body+=field(name,label,type,value,{id,required,min:type==='number'?0:undefined,max:name==='probability'||name==='lead_score'?100:undefined,full:type==='textarea'});
  }
  const dialog=modal({id:c.single.toLowerCase()+'-modal',title:(record.id?'Edit ':'Add ')+c.single,body,save:'Save '+c.single,onSave:async values=>{
    const payload={};for(const [name,,type] of defs){let value=values[name];if(['companies','contacts','leads','deals','users'].includes(type))value=value?Number(value):null;else if(type==='datetime-local')value=value?new Date(value).toISOString():null;else value=value===''?null:value;
      if(value!==null||!['status','priority'].includes(name))payload[name]=value;
    }
    if(entity==='deals'){payload.pipeline_id=Number(values.pipeline_id);payload.stage_id=Number(values.stage_id);if(payload.probability===null)delete payload.probability;}
    if(entity==='leads'&&payload.lead_score===null)delete payload.lead_score;
    if(record.id)await apiPut(`/${entity}/${record.id}`,payload);else await apiPost('/'+entity,payload);
    toast(c.single+' saved.');await after();
  }});
  bindRemoteSearch(dialog);
  if(entity==='deals')dialog.querySelector('[name=pipeline_id]').onchange=async e=>{try{const board=await apiGet(`/pipelines/${e.target.value}/board`);dialog.querySelector('[name=stage_id]').innerHTML=board.stages.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('');}catch(error){showError(dialog.querySelector('[data-form-error]'),error);}};
  return dialog;
}
export async function entityPage(entity){
  const c=configs[entity];const user=await initApp(c.title);if(!user)return;const main=document.querySelector('main');
  const id=new URLSearchParams(location.search).get('id');if(id){await detail(entity,Number(id),main);return;}
  main.innerHTML=heading(c.title,'Manage your '+c.title.toLowerCase()+' and their relationships.',`${canCreateOrEdit()?button('Add '+c.single,'create',true):''}${['companies','contacts','leads'].includes(entity)&&canCreateOrEdit()?button('Import CSV','import'):''}${button('Export CSV','export')}${entity==='tasks'&&canCreateOrEdit()?button('Log Activity','activity'):''}`)+`<section class="card"><div class="filters"><label class="search-label" for="search-${entity}">Search<input id="search-${entity}" type="search" placeholder="Filter ${entity}…"/></label>${c.filter?`<label for="filter-status">Status<select id="filter-status"><option value="">All statuses</option>${c.filter.map(s=>`<option value="${s}">${s.replaceAll('_',' ')}</option>`).join('')}</select></label>`:''}${c.sorts?`<label for="sort-by">Sort<select id="sort-by">${c.sorts.map(s=>`<option value="${s}">${s.replaceAll('_',' ')}</option>`).join('')}</select></label><label for="sort-dir">Direction<select id="sort-dir"><option value="asc">Ascending</option><option value="desc">Descending</option></select></label>`:''}</div><div id="record-table"></div><div id="pagination" class="pagination"></div></section>${entity==='tasks'?'<section class="card card-body section-gap"><h2>Recent activities</h2><div id="activities-list"></div></section>':''}`;
  let currentPage=1,sequence=0,timer;const container=document.getElementById('record-table');
  async function load(){const ownSequence=++sequence;container.innerHTML='<div class="loading" role="status">Loading records…</div>';try{
    const response=await apiGet('/'+entity,{page:currentPage,page_size:10,search:document.getElementById('search-'+entity).value,status:document.getElementById('filter-status')?.value,sort_by:document.getElementById('sort-by')?.value,sort_dir:document.getElementById('sort-dir')?.value});if(ownSequence!==sequence)return;
    container.innerHTML=response.items.length?table([...c.columns.map(([label])=>label),'Actions'],response.items.map(r=>`<tr>${c.columns.map(([,render])=>`<td>${render(r)}</td>`).join('')}<td><div class="actions">${canCreateOrEdit()?`<button data-edit-id="${r.id}">Edit</button>`:''}${entity==='tasks'&&canCreateOrEdit()?`<button data-complete-id="${r.id}">${r.status==='completed'?'Reopen':'Complete'}</button>`:''}${canDelete()?`<button data-delete-id="${r.id}" class="danger">Delete</button>`:''}</div></td></tr>`)):empty('No '+entity+' found','Create a record or adjust the search and filters.');
    const total=response.total;document.getElementById('pagination').innerHTML=`<span>Showing ${total?(currentPage-1)*10+1:0}–${Math.min(currentPage*10,total)} of ${total} records</span><div class="actions"><button data-page="prev"${currentPage<=1?' disabled':''}>Previous</button><span>Page ${currentPage} of ${Math.max(response.pages,1)}</span><button data-page="next"${currentPage>=response.pages?' disabled':''}>Next</button></div>`;
    main.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>{currentPage+=b.dataset.page==='next'?1:-1;load();});
    container.querySelectorAll('[data-edit-id]').forEach(b=>b.onclick=()=>recordForm(entity,response.items.find(r=>r.id===Number(b.dataset.editId)),load).catch(e=>toast(e.message)));
    container.querySelectorAll('[data-delete-id]').forEach(b=>b.onclick=async()=>{if(!confirm(`Delete this ${c.single.toLowerCase()}? This cannot be undone.`))return;b.disabled=true;try{await apiDelete(`/${entity}/${b.dataset.deleteId}`);toast(c.single+' deleted.');currentPage=1;await load();}catch(error){toast(error.message);b.disabled=false;}});
    container.querySelectorAll('[data-complete-id]').forEach(b=>b.onclick=async()=>{b.disabled=true;try{const r=response.items.find(r=>r.id===Number(b.dataset.completeId));await apiPut(`/tasks/${r.id}`,{status:r.status==='completed'?'pending':'completed'});await load();toast('Task status saved.');}catch(error){toast(error.message);b.disabled=false;}});
  }catch(error){if(ownSequence===sequence){showError(container,error);document.getElementById('pagination').innerHTML='<button data-retry>Retry</button>';main.querySelector('[data-retry]').onclick=load;}}}
  document.getElementById('search-'+entity).oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{currentPage=1;load();},250);};for(const id of ['filter-status','sort-by','sort-dir']){const input=document.getElementById(id);if(input)input.onchange=()=>{currentPage=1;load();};}
  main.querySelector('[data-action=create]')?.addEventListener('click',()=>recordForm(entity,{},load).catch(e=>toast(e.message)));
  main.querySelector('[data-action=import]')?.addEventListener('click',()=>openImport(entity,load));
  main.querySelector('[data-action=export]')?.addEventListener('click',async e=>{const b=e.currentTarget;b.disabled=true;try{const blob=await apiGet('/exports/'+entity);downloadText(await blob.text(),entity+'.csv');toast('Export downloaded.');}catch(error){toast(error.message);}finally{b.disabled=false;}});
  main.querySelector('[data-action=activity]')?.addEventListener('click',()=>activityForm({},()=>renderActivities(document.getElementById('activities-list'))).catch(e=>toast(e.message)));
  await load();if(entity==='tasks')await renderActivities(document.getElementById('activities-list'));
}
export async function activityForm(related={},after=()=>{}){
  const body=field('subject','Subject','text','',{required:true})+field('type','Activity Type','select','call',{choices:['call','email','meeting','note','follow_up']})+field('description','Details','textarea','',{full:true});
  return modal({id:'activity-modal',title:'Log Activity',body,save:'Save Activity',onSave:async data=>{await apiPost('/activities',{...data,...related});toast('Activity saved.');await after();}});
}
export async function renderActivities(container,params={}){try{const data=await apiGet('/activities',{page_size:20,...params});container.innerHTML=data.items.length?`<ul class="list">${data.items.map(a=>`<li><p><strong>${esc(a.subject)}</strong> ${badge(a.type)}</p><p class="subtle">${esc(a.description||'')}</p><time>${date(a.occurred_at)}</time></li>`).join('')}</ul>`:empty('No recent activities','Calls, meetings and notes appear here when you log them.');}catch(error){showError(container,error);}}
export async function detail(entity,id,main){
  try{const c=configs[entity],record=await apiGet(`/${entity}/${id}`);const name=record[c.key];const relatedField={companies:'company_id',contacts:'contact_id',leads:'lead_id',deals:'deal_id'}[entity];
    main.innerHTML=heading(name,`${c.single} profile`,`${canCreateOrEdit()?button('Edit','edit',true):''}${relatedField&&canCreateOrEdit()?button('Log Activity','activity'):''}${entity==='leads'&&canCreateOrEdit()&&record.status!=='converted'?button('Convert Lead','convert'):''}`)+`<p class="subtle"><a href="/${entity}">← All ${entity}</a></p><div class="details"><div class="card card-body"><h2>Record information</h2><div class="fields">${c.fields.filter(([key])=>record[key]!==null&&record[key]!==undefined).map(([key,label,type])=>`<div><span class="field-label">${esc(label)}</span><div class="field-value">${esc(type==='datetime-local'?date(record[key]):record[key])}</div></div>`).join('')}</div></div><section class="card card-body"><h2>Ownership and status</h2><p>${esc(record.owner?.name||'—')}</p>${record.status?badge(record.status):''}<p class="subtle section-gap">Created ${date(record.created_at)}</p></section></div><div id="related-records" class="section-gap"></div>${relatedField?'<section class="card card-body section-gap"><h2>Interaction history and notes</h2><div id="detail-activities"></div></section><section class="card card-body section-gap"><div class="page-heading"><h2>Attachments</h2><button data-action="upload">Upload file</button></div><div id="attachments"></div></section>':''}`;
    main.querySelector('[data-action=edit]')?.addEventListener('click',()=>recordForm(entity,record,()=>detail(entity,id,main)).catch(e=>toast(e.message)));
    main.querySelector('[data-action=activity]')?.addEventListener('click',()=>activityForm({[relatedField]:id},()=>detail(entity,id,main)));
    main.querySelector('[data-action=convert]')?.addEventListener('click',()=>convertForm(record,()=>detail(entity,id,main)).catch(e=>toast(e.message)));
    if(relatedField){const result=await apiGet(`/records/${entity}/${id}/related`);document.getElementById('related-records').innerHTML=`<div class="grid grid-2">${Object.entries(result).filter(([type])=>configs[type]).map(([type,rows])=>`<section class="card card-body"><h2>Related ${type}</h2>${rows.length?`<ul class="list">${rows.map(r=>`<li>${link(type,r.id,r.name||r.title)}${r.status?' '+badge(r.status):''}</li>`).join('')}</ul><p class="subtle">Up to 100 recent records. <a href="/${type}">Open all ${type}</a></p>`:empty('No related '+type,'Associated records will appear here.')}</section>`).join('')}</div>`;
      await renderActivities(document.getElementById('detail-activities'),{[relatedField]:id});await renderAttachments(entity,id,main);
    }
  }catch(error){showError(main,error);}
}
async function renderAttachments(entity,id,main){
  const container=document.getElementById('attachments'),config=await apiGet('/attachments/config');const files=await apiGet(`/records/${entity}/${id}/attachments`);
  container.innerHTML=files.length?`<div class="file-list">${files.map(f=>`<div class="file-row"><span>${esc(f.name)} <small class="subtle">${Math.ceil(f.size/1024)} KB${f.upload_state==='pending'?' - Pending upload; quota reserved until cleanup':''}</small></span><div class="actions"><button data-download-file="${f.id}">Download</button>${canCreateOrEdit()?`<button data-delete-file="${f.id}" class="danger">Delete</button>`:''}</div></div>`).join('')}</div>`:empty('No attachments','Upload a supported file to attach it to this record.');
  const upload=main.querySelector('[data-action=upload]');upload.disabled=!config.available||!canCreateOrEdit();if(!config.available)container.insertAdjacentHTML('beforeend','<p class="subtle">Private file storage is not configured. Ask your administrator to connect storage.</p>');
  upload.onclick=()=>modal({id:'attachment-modal',title:'Upload attachment',body:'<div class="field full"><label for="attachment-file">File</label><input id="attachment-file" type="file" accept=".pdf,.png,.jpg,.jpeg,.txt,.csv" required/><small>PDF, PNG, JPEG, TXT or CSV. Maximum 3 MB.</small></div>',save:'Upload',onSave:async()=>{const file=document.getElementById('attachment-file').files[0];if(file.size>3*1024*1024)throw new Error('Maximum upload size is 3 MB.');const data=new FormData();data.append('file',file);const {apiFetch}=await import('./api.js');await apiFetch(`/records/${entity}/${id}/attachments`,{method:'POST',body:data});toast('Attachment uploaded.');await renderAttachments(entity,id,main);}});
  main.querySelectorAll('[data-download-file]').forEach(b=>b.onclick=async()=>{try{const data=await apiGet(`/attachments/${b.dataset.downloadFile}/download`);location.assign(data.url);}catch(error){toast(error.message);}});
  main.querySelectorAll('[data-delete-file]').forEach(b=>b.onclick=async()=>{if(!confirm('Delete this attachment permanently?'))return;try{await apiDelete(`/attachments/${b.dataset.deleteFile}`);await renderAttachments(entity,id,main);}catch(error){toast(error.message);}});
}
async function convertForm(record,after){
  const pipelines=await apiGet('/pipelines',{page_size:100});if(!pipelines.items.length)throw new Error('Create a pipeline and stages in Deals before converting a lead.');
  const pipeline=pipelines.items[0],board=await apiGet(`/pipelines/${pipeline.id}/board`);
  const body=field('company_id','Existing company','select',record.company_id||'',{choices:await choices('companies',record.company_id)})+field('company_name','Or new company name')+field('contact_id','Existing contact','select',record.contact_id||'',{choices:await choices('contacts',record.contact_id)})+field('first_name','Or new contact first name')+field('last_name','New contact last name')+field('email','New contact email','email')+field('stage_id','Initial deal stage','select','',{required:true,choices:[['','Select stage…'],...board.stages.map(s=>[s.id,s.name])]});
  modal({id:'convert-lead-modal',title:'Convert Lead',body,save:'Convert Lead',onSave:async values=>{const data={...values,company_id:values.company_id?Number(values.company_id):null,contact_id:values.contact_id?Number(values.contact_id):null,pipeline_id:pipeline.id,stage_id:Number(values.stage_id)};for(const key of ['company_name','first_name','last_name','email'])if(!data[key])delete data[key];await apiPost(`/leads/${record.id}/convert`,data);toast('Lead converted.');await after();}});
}
