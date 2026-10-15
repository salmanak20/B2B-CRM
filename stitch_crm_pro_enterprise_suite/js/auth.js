import { apiGet,apiPost,setSessionRedirect } from './api.js';
import { API_BASE_URL,TOKEN_KEY,USER_KEY } from './config.js';
let currentUser=null;
// Remove obsolete plaintext browser storage without trusting its contents.
localStorage.removeItem(TOKEN_KEY);localStorage.removeItem(USER_KEY);
sessionStorage.removeItem(TOKEN_KEY);sessionStorage.removeItem(USER_KEY);
export const getCurrentUser=()=>currentUser;
export async function fetchCurrentUser(){currentUser=await apiGet('/auth/me');return currentUser;}
export async function login(email,password,remember=false){
  const response=await fetch(API_BASE_URL+'/auth/login?remember='+remember,{method:'POST',credentials:'include',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({username:email,password})});
  let data;try{data=await response.json();}catch{data=null;}
  if(!response.ok)throw new Error(typeof data?.detail==='string'?data.detail:'Unable to sign in. Please try again.');
  currentUser=data.user||await fetchCurrentUser();return currentUser;
}
export async function checkAuth(){try{return await fetchCurrentUser();}catch(e){if(e.status===401){if(!location.pathname.includes('login')&&!location.pathname.includes('/crm_pro_enterprise/'))location.replace('/login');return null;}throw e;}}
export async function logout(){setSessionRedirect(false);try{await apiPost('/auth/logout');currentUser=null;location.assign('/login');}catch(error){setSessionRedirect(true);throw error;}}
