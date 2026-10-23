import {API_BASE_URL} from './config.js';
import {apiGet,apiPost,setSessionRedirect} from './api.js';
import {field,showError,esc} from './ui.js';
setSessionRedirect(false);
const root=document.getElementById('app');
root.innerHTML=`<div class="login-page"><section class="login-card" aria-label="Super Admin sign in"><div class="brand"><span class="brand-mark">C</span><span>CRM Pro · Platform</span></div><h1>Super Admin sign in</h1><p class="subtle">Authorized platform identities only. Business ownership does not grant access.</p><div id="admin-login-error" role="alert"></div><div id="admin-login-step"></div><p><a href="/login">Business workspace sign in</a></p></section></div>`;
const step=document.getElementById('admin-login-step'),error=document.getElementById('admin-login-error');
function fail(e){showError(error,e);}
function password(){
  step.innerHTML=`<form id="admin-password">${field('email','Email','email','',{required:true,autocomplete:'username'})}${field('password','Password','password','',{required:true,autocomplete:'current-password'})}<button class="primary login-submit">Continue securely</button></form><p class="subtle">Your password stays in this private form. Authenticator verification follows.</p>`;
  step.querySelector('form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,button=form.querySelector('button');button.disabled=true;error.innerHTML='';try{
    const response=await fetch(API_BASE_URL+'/auth/login?platform=true',{method:'POST',credentials:'include',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({username:form.email.value,password:form.password.value})});
    form.password.value='';const result=await response.json();if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Unable to sign in');
    await mfa();
  }catch(e){fail(e);button.disabled=false;}};
}
async function mfa(){
  const state=await apiGet('/auth/platform/mfa');
  if(state.ready){location.assign('/platform-admin');return;}
  if(!state.factors.length){
    step.innerHTML='<h2>Set up your authenticator</h2><p>Use an authenticator app to protect every platform session.</p><button id="enroll-mfa" class="primary">Set up authenticator</button>';
    step.querySelector('button').onclick=async e=>{e.target.disabled=true;try{const result=await apiPost('/auth/platform/mfa/enroll');
      verification([{id:result.id,name:'New authenticator'}],`<p>Add this setup key privately to your authenticator app:</p><code class="mfa-secret">${esc(result.secret)}</code><p class="subtle">Keep this key private. It is shown only during setup.</p>`);
    }catch(e){fail(e);step.querySelector('button').disabled=false;}};
  }else verification(state.factors);
}
function verification(factors,setup=''){
  step.innerHTML=`<h2>Verify authenticator</h2>${setup}<form>${field('factor','Authenticator','select',factors[0].id,{choices:factors.map(f=>[f.id,f.name])})}${field('code','Six digit code','text','',{required:true,autocomplete:'one-time-code'})}<button class="primary login-submit">Verify and enter</button></form>`;
  const input=step.querySelector('[name=code]');input.inputMode='numeric';input.pattern='[0-9]{6}';input.maxLength=6;input.focus();
  step.querySelector('form').onsubmit=async e=>{e.preventDefault();const form=e.currentTarget,button=form.querySelector('button');button.disabled=true;try{await apiPost('/auth/platform/mfa/verify',{factor_id:form.factor.value,code:form.code.value});input.value='';location.assign('/platform-admin');}catch(e){fail(e);input.value='';button.disabled=false;}};
}
password();
