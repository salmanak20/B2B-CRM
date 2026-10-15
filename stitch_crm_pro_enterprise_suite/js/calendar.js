import {initApp} from './app.js';
import {apiGet} from './api.js';
import {heading,button,esc,showError,badge} from './ui.js';
async function start(){if(!await initApp('Calendar'))return;const main=document.querySelector('main');let month=new Date();month.setDate(1);let sequence=0;
  async function load(){const own=++sequence;const year=month.getFullYear(),index=month.getMonth(),last=new Date(year,index+1,0).getDate();const prefix=`${year}-${String(index+1).padStart(2,'0')}`;let rows=[],page=1;
    try{let response;do{response=await apiGet('/tasks',{due_after:prefix+'-01',due_before:prefix+'-'+last,page,page_size:100});rows.push(...response.items);page++;}while(page<=response.pages);if(own!==sequence)return;
      main.innerHTML=heading('Calendar',month.toLocaleDateString(undefined,{month:'long',year:'numeric'})+' · Task deadlines in UTC',button('Previous month','prev')+button('Today','today')+button('Next month','next'))+`<section class="calendar-grid" aria-label="Task calendar">${Array.from({length:last},(_,i)=>{const day=i+1,dayRows=rows.filter(r=>r.due_date?.slice(0,10)===prefix+'-'+String(day).padStart(2,'0'));return `<article class="calendar-day"><strong>${day}</strong>${dayRows.map(t=>`<a class="calendar-event" href="/tasks?id=${t.id}">${esc(t.title)} · ${esc(t.status.replaceAll('_',' '))}</a>`).join('')}</article>`;}).join('')}</section>`;
      main.querySelector('[data-action=prev]').onclick=()=>{month.setMonth(month.getMonth()-1);load();};main.querySelector('[data-action=next]').onclick=()=>{month.setMonth(month.getMonth()+1);load();};main.querySelector('[data-action=today]').onclick=()=>{month=new Date();month.setDate(1);load();};
    }catch(error){showError(main,error);}}
  await load();
}
start().catch(error=>showError(document.querySelector('main')||document.getElementById('app'),error));
