import {test,expect} from '@playwright/test';
import {authenticate,api,company,unique} from '../fixtures/live-api.js';

test('real cookie sessions isolate records and analytics after workspace switches',async({page})=>{
  await authenticate(page);const a=await company(page,unique('Private A'));
  const summaryA=await api(page,'GET','/dashboard/summary');
  await api(page,'POST','/auth/logout');await authenticate(page,'other');
  expect((await page.request.get(`/api/v1/companies/${a.id}`)).status()).toBe(404);
  expect((await page.request.put(`/api/v1/companies/${a.id}`,{data:{name:'Forbidden'}})).status()).toBe(404);
  expect((await page.request.get('/api/v1/dashboard/summary',{headers:{'X-Organization-ID':'1'}})).status()).toBe(403);
  const b=await company(page,unique('Private B'));
  await api(page,'POST','/auth/logout');await authenticate(page,'multi');
  await api(page,'POST','/auth/organization',{organization_id:1});await page.goto('/dashboard');
  const selector=page.getByLabel('Active workspace');await expect(selector).toBeVisible();
  expect((await api(page,'GET','/dashboard/summary')).total_companies).toBe(summaryA.total_companies);
  await selector.selectOption('2');await expect(page.getByLabel('Active workspace')).toHaveValue('2');
  await expect.poll(async()=>(await api(page,'GET','/auth/me')).organization_role).toBe('viewer');
  expect((await page.request.post('/api/v1/companies',{data:{name:'No elevation'}})).status()).toBe(403);
  expect((await page.request.get(`/api/v1/companies/${a.id}`)).status()).toBe(404);
  expect((await api(page,'GET',`/companies/${b.id}`)).name).toBe(b.name);
  await page.getByLabel('Active workspace').selectOption('1');
  await expect.poll(async()=>(await api(page,'GET','/auth/me')).organization_role).toBe('admin');
  expect((await page.request.get(`/api/v1/companies/${b.id}`)).status()).toBe(404);
});

test('revoked membership invalidates an existing cookie immediately',async({page,playwright})=>{
  await authenticate(page);const members=await api(page,'GET','/team/members');
  const target=members.members.find(m=>m.email==='revoked@qa.example.com');
  const employee=await playwright.request.newContext({baseURL:'http://127.0.0.1:5174'});
  try{
    expect((await employee.post('/api/v1/auth/login',{form:{username:target.email,password:process.env.E2E_PASSWORD}})).ok()).toBe(true);
    expect((await employee.get('/api/v1/companies')).status()).toBe(200);
    await api(page,'PUT',`/team/members/${target.user_id}`,{is_active:false});
    expect((await employee.get('/api/v1/companies')).status()).toBe(401);
    expect((await employee.post('/api/v1/auth/organization',{data:{organization_id:1}})).status()).toBe(401);
  }finally{await api(page,'PUT',`/team/members/${target.user_id}`,{is_active:true});await employee.dispose();}
});
