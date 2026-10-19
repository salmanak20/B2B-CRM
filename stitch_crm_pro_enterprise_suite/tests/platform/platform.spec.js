import {test,expect} from '@playwright/test';
test('platform dashboard shows metadata and submits audited management actions',async({page})=>{
  const writes=[],reads=[];
  await page.route('**/api/v1/**',async route=>{
    const r=route.request(),path=new URL(r.url()).pathname;reads.push(path);
    if(r.method()==='PUT'){writes.push({path,body:r.postDataJSON()});return route.fulfill({json:{ok:true}});}
    const data=path.endsWith('/summary')?{businesses:2,active:2,suspended:0,memberships:3}:
      path.endsWith('/organizations')?[{id:1,name:'Business A',slug:'a',is_suspended:false}]:
      path.endsWith('/organizations/1')?{name:'Business A',created_at:'2026-10-16T00:00:00Z',is_suspended:false,verified_owners:[{id:7,name:'Verified Owner',email:'owner@example.com'}]}:
      path.endsWith('/administrators')?[{user_id:3,name:'Operator',email:'operator@example.com',is_active:true}]:[];
    await route.fulfill({json:data});
  });
  await page.goto('/platform-admin');
  await expect(page.getByRole('heading',{name:'Platform Administration',exact:true})).toBeVisible();
  await expect(page.getByText('Registered businesses')).toBeVisible();
  await page.getByRole('button',{name:'Details',exact:true}).click();
  await expect(page.getByText('Verified Owner · owner@example.com')).toBeVisible();
  await page.getByRole('button',{name:'Close',exact:true}).click();
  await page.getByRole('button',{name:'Suspend',exact:true}).click();
  await page.getByLabel('Reason').fill('Security review');
  await page.getByRole('button',{name:'Confirm',exact:true}).click();
  await expect.poll(()=>writes.length).toBe(1);
  expect(writes[0]).toEqual({path:'/api/v1/platform/organizations/1',body:{is_suspended:true,reason:'Security review'}});
  await page.getByRole('button',{name:'Grant platform access'}).click();
  await page.getByLabel('Existing verified user ID').fill('8');await page.getByLabel('Reason').fill('Approved operator');
  await page.getByRole('button',{name:'Grant Access',exact:true}).click();
  await expect.poll(()=>writes.length).toBe(2);
  expect(writes[1].body).toEqual({is_active:true,reason:'Approved operator'});
  expect(reads.every(p=>p.includes('/platform/'))).toBeTruthy();
});
test('business users see access denied without platform controls',async({page})=>{
  await page.route('**/api/v1/platform/**',r=>r.fulfill({status:403,json:{detail:'Platform administrator access required'}}));
  await page.goto('/platform-admin');
  await expect(page.getByRole('alert')).toContainText('Platform administrator access required');
  await expect(page.getByRole('button',{name:'Grant platform access'})).toHaveCount(0);
});

for(const renewal of [false,true])test(`platform ${renewal?'renews':'approves'} a Pilot using explicit owner approval`,async({page})=>{
  const writes=[];
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    if(req.method()==='PUT'){
      writes.push({path,body:req.postDataJSON()});return route.fulfill({json:{ok:true}});
    }
    const data=path.endsWith('/summary')?{businesses:1,active:1,suspended:0,memberships:1}:
      path.endsWith('/organizations')?[{id:8,name:'Pilot staging',slug:'pilot-staging',is_suspended:false}]:
      path.endsWith('/subscriptions/8')?{plan:renewal?{code:'free_pilot'}:null,access_status:renewal?'expired_or_inactive':null,subscription:renewal?{status:'active',ends_at:'2026-10-18T00:00:00Z'}:null}:
      path.endsWith('/plans')?[{id:4,code:'free_pilot'}]:[];
    await route.fulfill({json:data});
  });
  await page.goto('/platform-admin');
  await page.getByRole('button',{name:'Free Pilot',exact:true}).click();
  await expect(page.getByRole('heading',{name:renewal?'Renew Free Pilot':'Approve Free Pilot',exact:true})).toBeVisible();
  await expect(page.getByText('Five users including the owner.',{exact:false})).toBeVisible();
  await page.getByLabel('Existing verified organization owner ID').fill('7');
  await page.getByLabel('Approval reason').fill('Approved staging business');
  await page.getByRole('button',{name:'Approve 30 days',exact:true}).click();
  await expect.poll(()=>writes.length).toBe(1);
  expect(writes[0]).toEqual({path:'/api/v1/platform/subscriptions/8',body:{plan_id:4,status:'active',enforcement_enabled:true,pilot_action:renewal?'extend':'activate',approved_owner_id:7,...(renewal?{expected_ends_at:'2026-10-18T00:00:00Z'}:{}),reason:'Approved staging business'}});
  expect(writes[0].body.starts_at).toBeUndefined();expect(writes[0].body.ends_at).toBeUndefined();
});
