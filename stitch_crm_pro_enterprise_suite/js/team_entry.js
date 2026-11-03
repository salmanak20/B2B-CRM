import {apiGet,apiPost} from './api.js';
import {field,modal} from './ui.js';
export async function createWorkspace(){
  await apiGet('/auth/onboarding');
  const key=sessionStorage.getItem('workspace-request-key')||crypto.randomUUID();
  sessionStorage.setItem('workspace-request-key',key);
  modal({id:'business-onboarding-modal',title:'Create your business workspace',save:'Create Workspace',body:
    '<p class="subtle field full">Your private workspace starts empty. Invite your team after setup.</p>'+field('name','Business name','text','',{required:true,full:true}),
    onSave:async values=>{await apiPost('/auth/onboarding',{name:values.name.trim(),request_key:key});sessionStorage.removeItem('workspace-request-key');location.assign('/dashboard');}});
}
export async function enterWorkspace(){
  const platform=await apiGet('/auth/platform-access');
  if(platform?.platform_mfa_required&&!new URLSearchParams(location.search).has('workspace')){location.assign('/platform-admin/login');return;}
  if(platform?.is_platform_admin&&!new URLSearchParams(location.search).has('workspace')){location.assign('/platform-admin');return;}
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
  if(!choices.length){await createWorkspace();return;}
  await apiPost('/auth/organization',{organization_id:choices[0].id});
  location.assign('/dashboard');
}
