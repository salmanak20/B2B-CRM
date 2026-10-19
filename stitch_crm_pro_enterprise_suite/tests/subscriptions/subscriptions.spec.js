import {test,expect} from '@playwright/test';
for(const configured of [true,false])test(`subscription page displays ${configured?'configured':'legacy'} database response without billing controls`,async({page})=>{
  const writes=[];
  await page.route('**/api/v1/**',async route=>{
    const r=route.request(),path=new URL(r.url()).pathname;
    if(r.method()!=='GET')writes.push(path);
    const plan={id:1,name:'Starter',price:null,currency:'USD',billing_interval:'month',seat_limit:5,entitlements:{analytics:true,exports:false}};
    const data=path.endsWith('/auth/me')?{id:1,name:'Owner',email:'owner@example.com',organization_id:1,role:{name:'admin'},organization_role:'owner',preferences:{}}:
      path.endsWith('/workspace')?{name:'Business A',timezone:'UTC',currency:'USD'}:
      path.endsWith('/subscription/plans')?(configured?[plan]:[]):
      path.endsWith('/subscription')?{plan:configured?plan:null,subscription:configured?{status:'active',enforcement_enabled:true,starts_at:'2026-10-17T00:00:00Z'}:null,seats:{active:2,pending:1,limit:configured?5:null},entitlements:{analytics:true,exports:!configured},billing_available:false}:[];
    await route.fulfill({json:data});
  });
  await page.goto('/subscription');
  await expect(page.getByRole('heading',{name:'Subscription',exact:true})).toBeVisible();
  await expect(page.getByText('Online payments are postponed.',{exact:false})).toBeVisible();
  await expect(page.getByText('Active memberships: 2',{exact:false})).toBeVisible();
  if(configured){await expect(page.getByText('Current plan: Starter')).toBeVisible();await expect(page.getByRole('cell',{name:'Contact administrator',exact:true})).toBeVisible();}
  else{await expect(page.getByText('No plans have been published.')).toBeVisible();await expect(page.getByText('Status: Not configured — existing access preserved')).toBeVisible();}
  await expect(page.getByRole('button',{name:/buy|upgrade|pay|checkout|billing/i})).toHaveCount(0);
  if(!configured){await expect(page.getByText('Seat limit: Not enforced - existing access preserved',{exact:false})).toBeVisible();await expect(page.getByText('Unlimited',{exact:false})).toHaveCount(0);}
  expect(writes).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
