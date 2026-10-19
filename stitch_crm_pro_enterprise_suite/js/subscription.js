import {initApp} from './app.js';
import {apiGet,apiPost} from './api.js';
import {esc,heading,table,showError,date} from './ui.js';
async function start(){
  const user=await initApp('Subscription');if(!user)return;
  const root=document.getElementById('main-content');
  try{
    const [current,plans]=await Promise.all([apiGet('/subscription'),apiGet('/subscription/plans')]);
    const s=current.subscription,seats=current.seats;
    const seatLimit=seats.limit??(s?.enforcement_enabled?'No limit configured':'Not enforced - existing access preserved');
    const billingMessage=current.test_billing_available?'Test billing only. Live payments are disabled.':'Online payments are postponed. Contact platform administration for business access or plan changes.';
    root.innerHTML=heading('Subscription','Plan, seat usage and workspace features.')+`<div class="card card-body"><h2>Current plan: ${esc(current.plan?.name||'Not configured')}</h2><p>Status: ${esc(s?.status||'Not configured — existing access preserved')}</p><p>Active memberships: ${esc(seats.active)} · Pending invitations: ${esc(seats.pending)} · Seat limit: ${esc(seatLimit)}</p>${s?`<p>Starts ${esc(date(s.starts_at))}${s.ends_at?' · Ends '+esc(date(s.ends_at)):''}</p>`:''}<p>Enforcement: ${s?.enforcement_enabled?'Enabled':'Not enabled'}</p><p class="subtle">${esc(billingMessage)}</p><h3>Feature access</h3>${Object.entries(current.entitlements).map(([f,on])=>`<span class="badge">${esc(f)}: ${on?'Included':'Not included'}</span>`).join(' ')}</div><section class="card card-body"><h2>Available plans</h2>${plans.length?table(['Plan','Price','Seats','Features'],plans.map(p=>`<tr><td>${esc(p.name)}</td><td>${p.code==='free_pilot'?'Free (30 days; manual renewal)':p.price===null?'Contact administrator':esc(p.currency+' '+p.price+' / '+p.billing_interval)}</td><td>${esc(p.seat_limit??'Unlimited')}</td><td>${esc(Object.keys(p.entitlements).filter(k=>p.entitlements[k]).join(', ')||'None configured')}</td></tr>`)):'<p>No plans have been published.</p>'}</section>`;
    if(current.test_billing_available&&current.can_manage_billing){
      root.insertAdjacentHTML('beforeend',`<section class="card card-body"><h2>Test billing</h2><p>Test mode only. Live payments are disabled. Checkout redirects never activate a plan.</p><div id="billing-error" role="alert"></div><div class="actions">${current.provider_status?'<button id="billing-portal">Manage test billing</button>':plans.map(p=>`<button data-test-checkout="${p.id}">Test checkout: ${esc(p.name)}</button>`).join('')}</div><div id="billing-history"></div></section>`);
      const fail=error=>showError(document.getElementById('billing-error'),error);
      document.querySelectorAll('[data-test-checkout]').forEach(button=>button.onclick=async()=>{
        button.disabled=true;const key='billing-request-'+user.organization_id+'-'+button.dataset.testCheckout;
        const requestKey=sessionStorage.getItem(key)||crypto.randomUUID();sessionStorage.setItem(key,requestKey);
        try{const result=await apiPost('/billing/checkout',{plan_id:Number(button.dataset.testCheckout),request_key:requestKey});location.assign(result.url);}catch(error){if(error.status===409)sessionStorage.removeItem(key);fail(error);button.disabled=false;}
      });
      const portal=document.getElementById('billing-portal');
      if(portal)portal.onclick=async()=>{portal.disabled=true;try{const result=await apiPost('/billing/portal');location.assign(result.url);}catch(error){fail(error);portal.disabled=false;}};
      if(current.provider_status){let page=1;const load=async()=>{const data=await apiGet('/billing/history',{page});document.getElementById('billing-history').innerHTML='<h3>Provider billing history (test)</h3>'+table(['Date','Status','Total','Refund','Invoice'],data.invoices.map(i=>`<tr><td>${esc(date(i.created_at))}</td><td>${esc(i.status)}</td><td>${esc(i.total_formatted)}</td><td>${esc(i.refunded_amount_formatted||'—')}</td><td>${i.invoice_url?`<a href="${esc(i.invoice_url)}" target="_blank" rel="noopener noreferrer">Invoice</a>`:'Pending'}</td></tr>`))+`<button id="billing-prev" ${page===1?'disabled':''}>Previous</button><button id="billing-next" ${data.invoices.length<20?'disabled':''}>Next</button>`;document.getElementById('billing-prev').onclick=()=>{page--;load().catch(fail);};document.getElementById('billing-next').onclick=()=>{page++;load().catch(fail);};};await load();}
    }
  }catch(error){showError(root,error);}
}
start();
