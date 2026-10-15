import { API_BASE_URL } from './config.js';
let redirectExpiredSession=true;
export function setSessionRedirect(enabled){redirectExpiredSession=enabled;}
export class ApiError extends Error { constructor(message,status,data){super(message);this.status=status;this.data=data;} }
export function getLoginUrl(){return '/login';}
export async function apiFetch(endpoint,options={}){
  const headers={...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...options.headers};
  let response;
  try{response=await fetch(API_BASE_URL+endpoint,{...options,headers,credentials:'include'});}
  catch{throw new ApiError('Unable to reach the server. Check your connection and try again.',0,null);}
  if(response.status===204)return null;
  const type=response.headers.get('content-type')||'';
  if(response.ok&&type.includes('text/csv'))return response.blob();
  let data;try{data=await response.json();}catch{data=null;}
  if(!response.ok){
    const detail=data?.detail;
    const message=Array.isArray(detail)?detail.map(e=>`${e.loc?.slice(1).join('.')||'Field'}: ${e.msg}`).join('; '):typeof detail==='string'?detail:response.status>=500?'The service is temporarily unavailable. Please try again.':`Request failed (${response.status}).`;
    if(redirectExpiredSession&&response.status===401&&!location.pathname.includes('login')&&!location.pathname.includes('crm_pro_enterprise')){
      location.assign('/login?expired=1');
    }
    throw new ApiError(message,response.status,data);
  }
  return data;
}
export function apiGet(endpoint,params={}){const q=new URLSearchParams(Object.entries(params).filter(([,v])=>v!==''&&v!==undefined&&v!==null));return apiFetch(endpoint+(q.size?'?'+q:''),{method:'GET'});}
export const apiPost=(endpoint,data={})=>apiFetch(endpoint,{method:'POST',body:JSON.stringify(data)});
export const apiPut=(endpoint,data={})=>apiFetch(endpoint,{method:'PUT',body:JSON.stringify(data)});
export const apiPatch=(endpoint,data={})=>apiFetch(endpoint,{method:'PATCH',body:JSON.stringify(data)});
export const apiDelete=endpoint=>apiFetch(endpoint,{method:'DELETE'});
