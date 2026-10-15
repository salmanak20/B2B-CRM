import '../css/app.css';
let lastTrigger=null;
document.addEventListener('click',event=>{const target=event.target.closest?.('button,a');if(target)lastTrigger=target;},{capture:true});
export const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const paths={grid:'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z',users:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8 M22 21v-2a4 4 0 0 0-3-3.87',company:'M4 21V3h12v18 M16 9h4v12 M8 7h4 M8 11h4 M8 15h4 M2 21h20',deal:'M3 7h18v14H3z M8 7V3h8v4 M3 12h18 M10 12v3h4v-3',task:'M9 3h6v4H9z M6 5H4v16h16V5h-2 M8 14l3 3 5-6',bell:'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9 M10 21h4',chart:'M3 3v18h18 M7 16v-4 M12 16V8 M17 16V5',settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2',search:'M21 21l-5-5 M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14',plus:'M12 5v14 M5 12h14',close:'M6 6l12 12 M6 18L18 6',menu:'M3 6h18 M3 12h18 M3 18h18',logout:'M9 21H3V3h6 M16 7l5 5-5 5 M7 12h14',calendar:'M3 5h18v16H3z M7 3v4 M17 3v4 M3 11h18',bolt:'M13 2L3 14h8l-1 8 11-13h-8z',download:'M12 3v12 M7 10l5 5 5-5 M3 17v4h18v-4',eye:'M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12 M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6'};
export const icon=(name)=>`<svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]||paths.grid}"/></svg>`;
export const money=(value,currency='USD')=>new Intl.NumberFormat(undefined,{style:'currency',currency,maximumFractionDigits:2}).format(Number(value||0));
export const badge=value=>`<span class="badge ${esc(value)}">${esc(value||'—').replaceAll('_',' ')}</span>`;
let displayTimezone='UTC';
export function setDisplayTimezone(value){try{new Intl.DateTimeFormat(undefined,{timeZone:value});displayTimezone=value;}catch{displayTimezone='UTC';}}
export const date=value=>{if(!value)return '—';const d=new Date(value.includes?.('T')&&!/([zZ]|[+-]\d{2}:\d{2})$/.test(value)?value+'Z':value);return Number.isNaN(d.valueOf())?'—':d.toLocaleString(undefined,{dateStyle:'medium',timeStyle:'short',timeZone:displayTimezone});};
export const empty=(title,message,action='')=>`<div class="empty">${icon('grid')}<h3>${esc(title)}</h3><p>${esc(message)}</p>${action}</div>`;
export function toast(message){document.querySelector('.toast')?.remove();const el=document.createElement('div');el.className='toast';el.setAttribute('role','status');el.textContent=message;document.body.append(el);setTimeout(()=>el.remove(),5000);}
export function showError(container,error){container.innerHTML=`<div class="error" role="alert">${esc(error.message||error)}</div>`;}
export function heading(title,description,actions=''){return `<div class="page-heading"><div><h1>${esc(title)}</h1><p class="subtle">${esc(description)}</p></div><div class="actions">${actions}</div></div>`;}
export const button=(text,action,primary=false)=>`<button ${action?`data-action="${esc(action)}"`:''} class="${primary?'primary':''}">${esc(text)}</button>`;
export function field(name,label,type='text',value='',options={}){
  const id=options.id||`field-${name}`;const required=options.required?' required':'';
  let control;
  if(type==='select')control=`<select id="${esc(id)}" name="${esc(name)}"${required}>${(options.choices||[]).map(o=>{const [v,l]=Array.isArray(o)?o:[o,o];return `<option value="${esc(v)}"${String(v)===String(value)?' selected':''}>${esc(l)}</option>`;}).join('')}</select>`;
  else if(type==='textarea')control=`<textarea id="${esc(id)}" name="${esc(name)}"${required}>${esc(value)}</textarea>`;
  else control=`<input id="${esc(id)}" name="${esc(name)}" type="${esc(type)}" value="${esc(value)}"${required}${options.min!==undefined?` min="${esc(options.min)}"`:''}${options.max!==undefined?` max="${esc(options.max)}"`:''}${type==='number'?' step="any"':''}${options.autocomplete?` autocomplete="${esc(options.autocomplete)}"`:''}/>`;
  return `<div class="field ${options.full?'full':''}"><label for="${esc(id)}">${esc(label)}${required?' <span aria-hidden="true">*</span>':''}</label>${control}${options.help?`<small>${esc(options.help)}</small>`:''}</div>`;
}
export function modal({id='record-modal',title,body,save='Save',onSave}){
  document.getElementById(id)?.remove();const opener=lastTrigger?.isConnected?lastTrigger:document.activeElement;const el=document.createElement('dialog');el.id=id;el.setAttribute('aria-labelledby',id+'-title');el.innerHTML=`<div class="modal-header"><h2 id="${id}-title">${esc(title)}</h2><button type="button" class="icon-button" data-close aria-label="Close dialog">${icon('close')}</button></div><form class="modal-body"><div class="fields">${body}</div><div data-form-error role="alert"></div><div class="modal-footer"><button type="button" data-close>Cancel</button><button type="submit" class="primary">${esc(save)}</button></div></form>`;
  document.body.append(el);el.querySelectorAll('[data-close]').forEach(b=>b.onclick=()=>el.close());el.addEventListener('close',()=>{el.remove();requestAnimationFrame(()=>{if(opener?.isConnected)opener.focus();});});
  el.querySelector('form').addEventListener('submit',async e=>{e.preventDefault();const submit=el.querySelector('[type=submit]');if(submit.disabled)return;submit.disabled=true;submit.textContent='Saving…';el.querySelector('[data-form-error]').innerHTML='';try{const result=await onSave(Object.fromEntries(new FormData(e.target)),el);if(result!==false)el.close();else{submit.disabled=false;submit.textContent=el.dataset.saveLabel||save;}}catch(error){showError(el.querySelector('[data-form-error]'),error);submit.disabled=false;submit.textContent=el.dataset.saveLabel||save;}});
  el.showModal();el.querySelector('input,select,textarea')?.focus();return el;
}
export function table(headers,rows){return `<div class="table-wrap"><table class="data-table"><thead><tr>${headers.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;}
export function downloadText(text,name,type='text/csv'){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
