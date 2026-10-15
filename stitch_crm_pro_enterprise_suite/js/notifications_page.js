import {initApp,refreshNotifications} from './app.js';
import {apiGet,apiPost,apiPatch,apiDelete} from './api.js';
import {esc,heading,button,empty,showError,toast,date,badge} from './ui.js';
async function start(){const user=await initApp('Notifications');if(!user)return;const main=document.querySelector('main');let onlyUnread=false;
  async function load(){try{const all=await apiGet('/notifications/',{limit:100});const rows=onlyUnread?all.filter(n=>!n.is_read):all;main.innerHTML=heading('Notifications','Assignments and due-task events from your workspace.',button('Mark all read','mark-all')+button('Check due tasks','check-due'))+`<section class="card card-body"><label for="unread-only" class="subtle"><input id="unread-only" type="checkbox"${onlyUnread?' checked':''}/> Show unread only</label><div id="notifications-page-list">${rows.length?`<ul class="list">${rows.map(n=>`<li><div class="page-heading"><div><p><strong>${esc(n.title)}</strong> ${n.is_read?'':badge('unread')}</p><p class="subtle">${esc(n.message)}</p><time>${date(n.created_at)}</time></div><div class="actions">${!n.is_read?`<button data-mark-read-id="${n.id}">Mark read</button>`:''}<button class="danger" data-delete-id="${n.id}">Delete</button></div></div></li>`).join('')}</ul><p class="subtle">Showing up to 100 recent notifications.</p>`:empty('No notifications',onlyUnread?'You have no unread notifications.':'Assignments and due-task reminders will appear here.')}</div></section>`;
    document.getElementById('unread-only').onchange=e=>{onlyUnread=e.target.checked;load();};
    main.querySelector('[data-action=mark-all]').onclick=()=>run(()=>apiPatch('/notifications/read-all'));
    main.querySelector('[data-action=check-due]').onclick=()=>run(()=>apiPost('/notifications/check-due'));
    main.querySelectorAll('[data-mark-read-id]').forEach(b=>b.onclick=()=>run(()=>apiPatch(`/notifications/${b.dataset.markReadId}/read`)));
    main.querySelectorAll('[data-delete-id]').forEach(b=>b.onclick=()=>{if(confirm('Delete this notification?'))run(()=>apiDelete('/notifications/'+b.dataset.deleteId));});await refreshNotifications();
  }catch(error){showError(main,error);}}
  let busy=false;async function run(fn){if(busy)return;busy=true;try{await fn();await load();toast('Notifications updated.');}catch(error){toast(error.message);}finally{busy=false;}}
  await load();
}
start().catch(error=>showError(document.querySelector('main')||document.getElementById('app'),error));
