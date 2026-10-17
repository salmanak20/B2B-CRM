import {enterWorkspace} from './team_entry.js';
import {login,fetchCurrentUser} from './auth.js';
import {apiGet,apiPost} from './api.js';
import {esc,icon,field,showError,modal} from './ui.js';
async function start(){
  const root=document.getElementById('app');root.innerHTML=`<div class="login-page"><section class="login-card" aria-label="Sign in"><div class="brand"><span class="brand-mark">CP</span><span>CRM Pro</span></div><h1>Welcome back</h1><p class="subtle">Sign in to your workspace.</p><div id="login-error-banner" role="alert" hidden></div><form id="login-form">${field('email','Email','email','',{id:'email',required:true,autocomplete:'username'})}<div class="field"><label for="password">Password <span aria-hidden="true">*</span></label><div class="password-wrap"><input id="password" name="password" type="password" required autocomplete="current-password"/><button type="button" id="show-password" class="icon-button quiet" aria-label="Show password" aria-pressed="false">${icon('eye')}</button></div></div><div class="login-options"><label><input type="checkbox" id="remember-me" name="remember"/>Remember me</label><button type="button" class="quiet" id="forgot-password">Forgot password?</button></div><button type="submit" class="primary login-submit">Sign In</button></form><p class="session-policy" id="session-policy">Your session is protected by a secure server cookie.</p></section></div>`;
  const form=document.getElementById('login-form'),banner=document.getElementById('login-error-banner');const fail=error=>{banner.hidden=false;showError(banner,error);};
  document.getElementById('show-password').onclick=e=>{const btn=e.currentTarget,input=document.getElementById('password');input.type=input.type==='password'?'text':'password';btn.setAttribute('aria-label',input.type==='password'?'Show password':'Hide password');btn.setAttribute('aria-pressed',String(input.type==='text'));};
  form.addEventListener('submit',async e=>{e.preventDefault();const submit=form.querySelector('[type=submit]');if(submit.disabled)return;submit.disabled=true;submit.textContent='Signing in...';banner.hidden=true;try{await login(form.email.value.trim(),form.password.value,form.remember.checked);await enterWorkspace();}catch(error){fail(error);submit.disabled=false;submit.textContent='Sign In';}});
  let config;try{config=await apiGet('/auth/config');document.getElementById('session-policy').textContent=`Standard session: ${config.session_hours} hours, ending when this browser session closes. Remember me: up to ${config.remember_days} days. Signing out revokes this session.`;}catch(error){fail(error);}
  if(config?.business_registration_enabled){
    const button=document.createElement('button');button.type='button';button.className='quiet';button.textContent='Register business account';
    document.querySelector('.login-card').append(button);
    button.onclick=()=>modal({id:'business-signup-modal',title:'Register business account',save:'Register',body:
      field('name','Full name','text','',{required:true,autocomplete:'name'})+field('email','Email','email','',{required:true,autocomplete:'email'})+field('password','Password','password','',{required:true,autocomplete:'new-password',help:'At least 12 characters, up to 72 UTF-8 bytes.'}),
      onSave:async values=>{const result=await apiPost('/auth/business-signup',values);banner.hidden=false;banner.innerHTML=`<p class="success" role="status">${esc(result.message)}</p>`;}});
  }
  const forgot=document.getElementById('forgot-password');forgot.disabled=!config?.recovery_available;if(forgot.disabled)forgot.title='Account recovery is available when the identity provider is configured.';
  forgot.onclick=()=>modal({id:'recovery-modal',title:'Reset your password',save:'Send recovery email',body:field('email','Account email','email',form.email.value,{required:true,autocomplete:'email'}),onSave:async data=>{const r=await apiPost('/auth/forgot-password',data);banner.hidden=false;banner.innerHTML=`<p class="success" role="status">${esc(r.message)}</p>`;}});
  const params=new URLSearchParams(location.search);
  if(params.get('token_hash')){
    try{const verified=await apiPost('/auth/recovery/verify',{token_hash:params.get('token_hash'),type:params.get('type')||'recovery'});history.replaceState(null,'','/login');if(!verified.recovery){await enterWorkspace();return;}modal({id:'reset-password-modal',title:'Set your password',save:'Set password',body:field('password','New password','password','',{required:true,help:'At least 12 characters, up to 72 UTF-8 bytes.',autocomplete:'new-password'}),onSave:async data=>{const r=await apiPost('/auth/password',data);banner.hidden=false;banner.innerHTML=`<p class="success">${esc(r.message)}</p>`;}});}catch(error){history.replaceState(null,'','/login');fail(error);}return;
  }
  try{await enterWorkspace();}catch(error){if(error.status!==401)fail(error);else if(params.get('expired'))fail(new Error('Your session expired. Please sign in again.'));}
}
start().catch(error=>showError(document.getElementById('app'),error));
