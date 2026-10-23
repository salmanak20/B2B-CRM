import {initApp} from './app.js';
import {apiGet,apiPost,apiPut,apiDelete} from './api.js';
import {isAdmin,getRoleDisplayName} from './rbac.js';
import {esc,heading,button,field,modal,table,empty,showError,toast,badge,date} from './ui.js';
async function start(){
  const user=await initApp('User Management');if(!user)return;
  const main=document.querySelector('main');
  if(!isAdmin()){showError(main,new Error('Owner or administrator access is required.'));return;}
  async function load(){try{
    const [team,invitations,logs]=await Promise.all([apiGet('/team/members'),apiGet('/team/invitations'),apiGet('/audit-logs/',{limit:100})]);
    const roles=team.roles.map(role=>[role,getRoleDisplayName(role)]);
    main.innerHTML=heading('Team Management','Manage access to this organization. Roles in other organizations remain independent.',button('Invite Employee','create',true))+
      `<section class="card">${table(['Name','Email','Organization role','Status','Actions'],team.members.map(m=>`<tr><td>${esc(m.name)}${m.is_self?' (you)':''}</td><td>${esc(m.email)}</td><td>${esc(getRoleDisplayName(m.role))}</td><td>${badge(m.is_active?'active':'inactive')}</td><td>${m.can_manage?`<button data-member-edit="${m.user_id}">Change access</button> <button data-member-remove="${m.user_id}">Remove</button>`:'Owner-controlled'}</td></tr>`))}</section>`+
      `<section class="card card-body section-gap"><h2>Pending invitations</h2>${invitations.length?table(['Name','Email','Role','Expires','Actions'],invitations.map(i=>`<tr><td>${esc(i.name)}</td><td>${esc(i.email)}</td><td>${esc(getRoleDisplayName(i.role))}</td><td>${date(i.expires_at)}</td><td>${i.can_manage===false?'Owner-controlled':`<button data-invitation-cancel="${i.id}">Revoke invitation</button>`}</td></tr>`)):empty('No pending invitations','Employees receive access after signing in and accepting their invitation.')}</section>`+
      `<section class="card card-body section-gap"><h2>Audit log</h2>${logs.length?table(['Time','Actor','Action','Description'],logs.map(l=>`<tr><td>${date(l.timestamp)}</td><td>${esc(team.members.find(m=>m.user_id===l.user_id)?.name||'User #'+l.user_id)}</td><td>${esc(l.action)}</td><td>${esc(l.description||'—')}</td></tr>`)):empty('No audit entries','Organization access changes appear here.')}</section>`;
    main.insertAdjacentHTML('afterbegin',`<div class="card card-body"><p>Seats used: ${esc(team.seats?.used??'—')} / ${esc(team.seats?.limit??'Requires review')} · Remaining: ${esc(team.seats?.remaining??'—')}</p>${team.email_delivery_available===false?'<p class="subtle">Email delivery is unavailable. Verified existing users can accept an authorized invitation after signing in. New identities remain pending; no account or password is created.</p>':''}</div>`);
    main.querySelector('[data-action=create]').onclick=()=>modal({id:'employee-modal',title:'Invite Employee',save:'Record Invitation',body:
      field('name','Full Name','text','',{required:true})+field('email','Email','email','',{required:true})+
      field('role','Organization Role','select','sales_rep',{required:true,choices:roles})+
      '<p class="subtle">Employees must verify sign-in and accept before receiving access. Invitations expire after seven days.</p>',
      onSave:async values=>{await apiPost('/team/invitations',values);toast('Invitation recorded. Access requires verified acceptance.');await load();}});
    main.querySelectorAll('[data-member-edit]').forEach(b=>b.onclick=()=>{
      const m=team.members.find(m=>m.user_id===Number(b.dataset.memberEdit));
      modal({id:'member-modal',title:'Change organization access',save:'Save Access',body:
        `<p>${esc(m.name)}</p>`+field('role','Organization Role','select',m.role,{required:true,choices:roles})+
        field('is_active','Status','select',String(m.is_active),{choices:[['true','Active'],['false','Inactive']]}),
        onSave:async values=>{await apiPut(`/team/members/${m.user_id}`,{role:values.role,is_active:values.is_active==='true'});toast('Organization access updated.');await load();}});
    });
    main.querySelectorAll('[data-member-remove]').forEach(b=>b.onclick=()=>modal({id:'remove-member-modal',title:'Remove member?',save:'Remove Access',body:
      '<p>Remove access to this organization. Existing CRM records and their ownership will be preserved.</p>',
      onSave:async()=>{await apiDelete(`/team/members/${b.dataset.memberRemove}`);toast('Organization access removed.');await load();}}));
    main.querySelectorAll('[data-invitation-cancel]').forEach(b=>b.onclick=async()=>{
      b.disabled=true;try{await apiDelete(`/team/invitations/${b.dataset.invitationCancel}`);toast('Invitation revoked.');await load();}catch(error){toast(error.message);b.disabled=false;}
    });
  }catch(error){showError(main,error);}}
  await load();
}
start().catch(error=>showError(document.querySelector('main')||document.getElementById('app'),error));
