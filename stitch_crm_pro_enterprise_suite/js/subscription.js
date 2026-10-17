import {initApp} from './app.js';
import {apiGet} from './api.js';
import {esc,heading,table,showError,date} from './ui.js';
async function start(){
  if(!await initApp('Subscription'))return;
  const root=document.getElementById('main-content');
  try{
    const [current,plans]=await Promise.all([apiGet('/subscription'),apiGet('/subscription/plans')]);
    const s=current.subscription,seats=current.seats;
    root.innerHTML=heading('Subscription','Plan, seat usage and workspace features.')+`<div class="card card-body"><h2>Current plan: ${esc(current.plan?.name||'Not configured')}</h2><p>Status: ${esc(s?.status||'Not configured — existing access preserved')}</p><p>Active memberships: ${esc(seats.active)} · Pending invitations: ${esc(seats.pending)} · Seat limit: ${esc(seats.limit??'Unlimited')}</p>${s?`<p>Starts ${esc(date(s.starts_at))}${s.ends_at?' · Ends '+esc(date(s.ends_at)):''}</p>`:''}<p>Enforcement: ${s?.enforcement_enabled?'Enabled':'Not enabled'}</p><p class="subtle">Billing is unavailable until a real provider is configured. Contact your administrator for plan changes.</p><h3>Feature access</h3>${Object.entries(current.entitlements).map(([f,on])=>`<span class="badge">${esc(f)}: ${on?'Included':'Not included'}</span>`).join(' ')}</div><section class="card card-body"><h2>Available plans</h2>${plans.length?table(['Plan','Price','Seats','Features'],plans.map(p=>`<tr><td>${esc(p.name)}</td><td>${p.price===null?'Contact administrator':esc(p.currency+' '+p.price+' / '+p.billing_interval)}</td><td>${esc(p.seat_limit??'Unlimited')}</td><td>${esc(Object.keys(p.entitlements).filter(k=>p.entitlements[k]).join(', ')||'None configured')}</td></tr>`)):'<p>No plans have been published.</p>'}</section>`;
  }catch(error){showError(root,error);}
}
start();
