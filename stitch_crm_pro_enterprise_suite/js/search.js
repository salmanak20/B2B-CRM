import {apiGet} from './api.js';
import {esc} from './ui.js';
export function initGlobalSearch(){
  const input=document.querySelector('[data-global-search]');if(!input)return;
  const list=document.createElement('div');list.className='global-search-dropdown';list.hidden=true;list.id='search-results';list.setAttribute('role','region');list.setAttribute('aria-label','Search results');input.setAttribute('aria-controls',list.id);input.parentElement.append(list);
  let timer,sequence=0;
  input.addEventListener('input',()=>{clearTimeout(timer);const request=++sequence;const q=input.value.trim();if(q.length<2){list.hidden=true;return;}timer=setTimeout(async()=>{list.hidden=false;list.textContent='Searching…';try{const data=await apiGet('/search/',{q});if(request!==sequence)return;let html='';for(const [type,items] of Object.entries(data)){if(!items.length)continue;html+=`<h3>${esc(type)} (${items.length})</h3>`+items.map(r=>`<a class="search-result" href="/${type==='tasks'?'tasks':type}?id=${r.id}">${esc(r.name||r.title)}${r.email?`<small class="subtle"> · ${esc(r.email)}</small>`:''}</a>`).join('');}list.innerHTML=html||'<p class="subtle">No matching records.</p>';}catch(error){list.textContent=error.message;}},300);});
  document.addEventListener('click',e=>{if(!input.parentElement.contains(e.target))list.hidden=true;});input.addEventListener('keydown',e=>{if(e.key==='Escape')list.hidden=true;if(e.key==='ArrowDown'){e.preventDefault();list.querySelector('a')?.focus();}});
}
