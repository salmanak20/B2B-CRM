import {apiGet,apiPut} from './api.js';
import {logout} from './auth.js';
import {esc,heading,table,field,modal,showError,date} from './ui.js';
const root=document.getElementById('app');let offset=0;
async function start(){
  await apiGet('/platform/summary');
  root.innerHTML=`<div class="card card-body"><div class="actions"><a class="brand" href="/platform-admin">CRM Pro · Platform</a><a href="/login?workspace=1">My CRM workspace</a><button id="platform-logout">Sign out</button></div>${heading('Platform Administration','Business metadata and platform permissions. Customer CRM records remain private.')}<div id="platform-error" role="alert"></div><div id="platform-metrics" class="kpis"></div><section class="card-body"><h2>Businesses</h2><form id="business-filter" class="actions">${field('q','Business name','search')}${field('status','Status','select','all',{choices:[['all','All'],['active','Active'],['suspended','Suspended']]})}<button>Search</button></form><div id="business-list"></div><div class="actions"><button id="previous-businesses">Previous</button><button id="next-businesses">Next</button></div></section><section class="card-body"><h2>Platform administrators</h2><button id="grant-admin">Grant platform access</button><div id="admin-list"></div></section><section class="card-body"><h2>Recent platform activity</h2><div id="platform-activity"></div></section></div>`;
  document.getElementById('platform-logout').onclick=()=>logout();
  document.getElementById('business-filter').onsubmit=e=>{e.preventDefault();offset=0;refresh().catch(fail);};
  document.getElementById('previous-businesses').onclick=()=>{offset=Math.max(0,offset-100);refresh().catch(fail);};
  document.getElementById('next-businesses').onclick=()=>{offset+=100;refresh().catch(fail);};
  document.getElementById('grant-admin').onclick=()=>modal({title:'Grant platform access',save:'Grant Access',body:field('user_id','Existing verified user ID','number','',{required:true,min:1})+field('reason','Reason','text','',{required:true}),onSave:async v=>{await apiPut('/platform/administrators/'+Number(v.user_id),{is_active:true,reason:v.reason});await refresh();}});
  await refresh();
}
function fail(error){showError(document.getElementById('platform-error')||root,error);}
async function refresh(){
  const form=document.getElementById('business-filter');
  const [s,orgs,admins,events]=await Promise.all([apiGet('/platform/summary'),apiGet('/platform/organizations',{q:form.q.value,status:form.status.value,offset}),apiGet('/platform/administrators'),apiGet('/platform/activity')]);
  document.getElementById('platform-metrics').innerHTML=[['Registered businesses',s.businesses],['Active',s.active],['Suspended',s.suspended],['Organization memberships',s.memberships]].map(([label,value])=>`<div class="card kpi"><span class="kpi-label">${esc(label)}</span><div class="kpi-value">${esc(value)}</div></div>`).join('');
  document.getElementById('business-list').innerHTML=table(['Business','Slug','Status','Actions'],orgs.map(o=>`<tr><td>${esc(o.name)}</td><td>${esc(o.slug)}</td><td>${o.is_suspended?'Suspended':'Active'}</td><td><button data-details="${o.id}">Details</button><button data-pilot="${o.id}">Free Pilot</button><button data-suspend="${o.id}">${o.is_suspended?'Reactivate':'Suspend'}</button></td></tr>`));
  document.getElementById('previous-businesses').disabled=offset===0;document.getElementById('next-businesses').disabled=orgs.length<100;
  document.querySelectorAll('[data-details]').forEach(button=>button.onclick=async()=>{try{const o=await apiGet('/platform/organizations/'+button.dataset.details);modal({title:o.name,save:'Close',body:`<p class="field full">Created ${esc(date(o.created_at))}. ${o.is_suspended?'Suspended':'Active'}.</p><div class="field full"><strong>Verified active owners</strong>${o.verified_owners.length?o.verified_owners.map(u=>`<p>ID ${esc(u.id)}: ${esc(u.name)} · ${esc(u.email)}</p>`).join(''):'<p>None verified.</p>'}</div>`,onSave:async()=>{}});}catch(e){fail(e);}});
  document.querySelectorAll('[data-suspend]').forEach(button=>button.onclick=()=>{const o=orgs.find(o=>o.id===Number(button.dataset.suspend));modal({title:o.is_suspended?'Reactivate business':'Suspend business',save:'Confirm',body:field('reason','Reason','text','',{required:true}),onSave:async v=>{await apiPut('/platform/organizations/'+o.id,{is_suspended:!o.is_suspended,reason:v.reason});await refresh();}});});
  document.querySelectorAll('[data-pilot]').forEach(button=>button.onclick=async()=>{
    try{
      const org=Number(button.dataset.pilot),current=await apiGet('/platform/subscriptions/'+org);
      const renewal=current.plan?.code==='free_pilot';
      modal({title:renewal?'Renew Free Pilot':'Approve Free Pilot',save:'Approve 30 days',body:`<p class="field full">Five users including the owner. All four features, existing security limits. Access stops at expiry; no automatic renewal. This does not lift a separate organization suspension.</p>${current.subscription?`<p class="field full">Current status: ${esc(current.access_status||current.subscription.status)}. Ends: ${esc(date(current.subscription.ends_at))}</p>`:''}`+field('approved_owner_id','Existing verified organization owner ID','number','',{required:true,min:1})+field('reason','Approval reason','text','',{required:true}),onSave:async v=>{
        const plans=await apiGet('/platform/plans');let plan=plans.find(p=>p.code==='free_pilot');
        if(!plan)plan=await apiPut('/platform/plans/free_pilot',{name:'Free Pilot',currency:'USD',price:0,billing_interval:'month',seat_limit:5,entitlements:{analytics:true,exports:true,workflows:true,attachments:true},published:true,reason:v.reason});
        await apiPut('/platform/subscriptions/'+org,{plan_id:plan.id,status:'active',enforcement_enabled:true,pilot_action:renewal?'extend':'activate',approved_owner_id:Number(v.approved_owner_id),...(renewal?{expected_ends_at:current.subscription.ends_at}:{}),reason:v.reason});
        await refresh();
      }});
    }catch(error){fail(error);}
  });
  document.getElementById('admin-list').innerHTML=table(['Name','Email','Access','Actions'],admins.map(a=>`<tr><td>${esc(a.name)}</td><td>${esc(a.email)}</td><td>${a.is_active?'Active':'Revoked'}</td><td>${a.is_active?`<button data-revoke="${a.user_id}">Revoke</button>`:''}</td></tr>`));
  document.querySelectorAll('[data-revoke]').forEach(button=>button.onclick=()=>modal({title:'Revoke platform access',save:'Revoke Access',body:field('reason','Reason','text','',{required:true}),onSave:async v=>{await apiPut('/platform/administrators/'+button.dataset.revoke,{is_active:false,reason:v.reason});await refresh();}}));
  document.getElementById('platform-activity').innerHTML=table(['When','Actor ID','Action','Target ID','Reason'],events.map(a=>`<tr><td>${esc(date(a.created_at))}</td><td>${esc(a.actor_id)}</td><td>${esc(a.action)}</td><td>${esc(a.target_id)}</td><td>${esc(a.reason)}</td></tr>`));
}
start().catch(fail);
