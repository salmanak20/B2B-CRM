import {apiGet,apiPost} from './api.js';
import {esc,toast} from './ui.js';
import {createWorkspace} from './team_entry.js';

export async function initWorkspaceSwitcher(user){
  let choices,config;
  try{[choices,config]=await Promise.all([apiGet('/auth/organizations'),apiGet('/auth/config')]);}catch{return;}
  const host=document.getElementById('workspace-selector');
  if(!host)return;
  if(choices.length>1){
    host.innerHTML=`<select aria-label="Active workspace">${choices.map(o=>`<option value="${o.id}" ${o.id===user.organization_id?'selected':''}>${esc(o.name)}</option>`).join('')}</select>`;
    host.querySelector('select').onchange=async e=>{const select=e.currentTarget;select.disabled=true;try{await apiPost('/auth/organization',{organization_id:Number(select.value)});location.assign('/dashboard');}catch(error){select.value=String(user.organization_id);select.disabled=false;toast(error.message);}};
  }
  if(config.business_registration_enabled){
    const button=document.createElement('button');button.type='button';button.className='quiet';button.textContent='New workspace';
    button.onclick=()=>createWorkspace().catch(error=>toast(error.message));host.append(button);
  }
}
