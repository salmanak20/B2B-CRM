import {esc,table} from './ui.js';
export const resourceLabel=key=>({storage_bytes:'Attachment storage (bytes)',workflow_executions:'Workflow executions this period',seats:'Seats including pending invitations'}[key]||key.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase()));
export function usageTable(resources={}){
  return table(['Resource','Used','Allowed','Remaining','Usage'],Object.entries(resources).map(([key,r])=>`<tr><td>${esc(resourceLabel(key))}</td><td>${esc(r.used)}</td><td>${esc(r.limit??'Requires review')}</td><td>${esc(r.remaining??'—')}</td><td>${r.percent===null||r.percent===undefined?'—':`<progress max="100" value="${Math.min(100,r.percent)}" aria-label="${esc(resourceLabel(key))} usage"></progress> ${esc(r.percent)}%`}</td></tr>`));
}
export function trendsTable(trends=[]){
  return trends.length?table(['Period (UTC)','Resource','Created','Updated','Deleted','Units added','Units removed'],trends.map(r=>`<tr><td>${esc(r.period)}</td><td>${esc(resourceLabel(r.resource))}</td><td>${esc(r.created)}</td><td>${esc(r.updated)}</td><td>${esc(r.deleted)}</td><td>${esc(r.added_units)}</td><td>${esc(r.removed_units)}</td></tr>`)):'<p>No recorded writes for this period.</p>';
}
