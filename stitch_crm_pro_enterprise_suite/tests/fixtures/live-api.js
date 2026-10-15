import {expect} from '@playwright/test';
export const email=role=>(role||'admin')+'@qa.example.com';
export const unique=label=>label+' '+Date.now()+' '+Math.random().toString(36).slice(2,7);
export async function authenticate(page,role='admin'){
  const response=await page.request.post('/api/v1/auth/login?remember=true',{form:{username:email(role),password:process.env.E2E_PASSWORD}});
  expect(response.status(),await response.text()).toBe(200);
}
export async function api(page,method,path,data){
  const response=await page.request.fetch('/api/v1'+path,{method,data});
  expect(response.ok(),await response.text()).toBeTruthy();return response.status()===204?null:response.json();
}
export const company=async(page,name=unique('Company'))=>api(page,'POST','/companies',{name,industry:'technology'});
export const lead=async(page,title=unique('Lead'))=>api(page,'POST','/leads',{title,status:'new',source:'website'});
export async function pipeline(page){const p=await api(page,'POST','/pipeline-setup',{pipeline:{name:unique('Sales process')},stages:[{name:'New',order:1,probability:10,is_closed:false},{name:'Won',order:2,probability:100,is_closed:true,is_won:true},{name:'Lost',order:3,probability:0,is_closed:true,is_lost:true}]});const board=await api(page,'GET',`/pipelines/${p.id}/board`);return {...p,stages:board.stages};}
export async function loginUI(page,role='admin'){
  await page.goto('/login');await page.getByLabel(/^Email/).fill(email(role));await page.getByLabel(/^Password/).fill(process.env.E2E_PASSWORD);await page.locator('#login-form [type=submit]').click();await expect(page).toHaveURL(/\/dashboard$/);await expect(page.locator('[data-kpi=total_leads]')).toBeVisible();
}
export function collectPageErrors(page){const errors=[];page.on('pageerror',e=>errors.push(e.message));return errors;}
