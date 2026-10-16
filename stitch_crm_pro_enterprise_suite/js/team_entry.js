import {apiGet,apiPost} from './api.js';
import {field,modal} from './ui.js';
export async function enterWorkspace(){
  const invitations=await apiGet('/auth/invitations');
  if(invitations.length){
    modal({id:'accept-invitation-modal',title:'Organization invitations',save:'Accept Invitation',body:
      field('invitation_id','Organization','select',invitations[0].id,{required:true,choices:invitations.map(i=>[i.id,`${i.organization_name} (${i.role})`])}),
      onSave:async values=>{const result=await apiPost(`/auth/invitations/${Number(values.invitation_id)}/accept`);await apiPost('/auth/organization',result);location.assign('/dashboard');}});return;
  }
  const choices=await apiGet('/auth/organizations');
  if(choices.length>1){
    modal({id:'choose-organization-modal',title:'Choose organization',save:'Continue',body:
      field('organization_id','Organization','select',choices[0].id,{required:true,choices:choices.map(o=>[o.id,o.name])}),
      onSave:async values=>{await apiPost('/auth/organization',{organization_id:Number(values.organization_id)});location.assign('/dashboard');}});return;
  }
  if(!choices.length)throw new Error('No active organization access. Ask your administrator for an invitation.');
  location.assign('/dashboard');
}
