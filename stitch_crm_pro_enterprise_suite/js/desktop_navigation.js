import {openExternal,routeUrl} from './config.js';
import '../css/desktop.css';

const connectionStatus=document.createElement('aside');
connectionStatus.className='desktop-connection-status';
connectionStatus.setAttribute('role','status');
connectionStatus.setAttribute('aria-live','polite');
connectionStatus.innerHTML='<span data-connection-message></span><button type="button" data-connection-retry>Retry</button>';
document.body.prepend(connectionStatus);
connectionStatus.querySelector('[data-connection-retry]').addEventListener('click',()=>location.reload());
function showConnection(message){connectionStatus.querySelector('[data-connection-message]').textContent=message;connectionStatus.classList.add('visible');}
window.addEventListener('offline',()=>showConnection('Internet connection lost. Your latest changes were not confirmed.'));
window.addEventListener('online',()=>showConnection('Connection restored. Retry to refresh CRM data.'));
window.addEventListener('crm:connection-error',()=>showConnection('Unable to reach the CRM service. Check your connection and retry.'));
if(!navigator.onLine)showConnection('Internet connection lost. Your latest changes were not confirmed.');

document.addEventListener('click',async event=>{
  if(event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
  const target=event.target instanceof Element?event.target:event.target?.parentElement;
  const anchor=target?.closest('a[href]');
  if(!anchor||anchor.hasAttribute('download'))return;
  let destination;
  try{destination=new URL(anchor.href);}catch{return;}
  if(destination.origin!==location.origin){
    event.preventDefault();
    if(destination.protocol!=='https:')return;
    try{await openExternal(destination.href);}catch{window.alert('This external destination is not approved for the desktop app.');}
    return;
  }
  if(anchor.target==='_blank')return;
  const current=destination.pathname+destination.search+destination.hash;
  const route=routeUrl(current);
  if(route!==current){event.preventDefault();location.assign(route);}
},true);
