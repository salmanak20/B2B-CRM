import {test,expect} from '@playwright/test';

test('dedicated admin login keeps provider tokens private and requires authenticator verification',async({page})=>{
  let verified=false;
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    if(path==='/api/v1/auth/login'){
      expect(new URL(req.url()).searchParams.get('platform')).toBe('true');
      return route.fulfill({json:{user:{id:3}}});
    }
    if(path.endsWith('/mfa'))return route.fulfill({json:{ready:false,required:true,factors:[{id:'00000000-0000-0000-0000-000000000003',name:'Authenticator'}]}});
    if(path.endsWith('/mfa/verify')){expect(req.postDataJSON().code).toBe('123456');verified=true;return route.fulfill({json:{ok:true}});}
    if(path.endsWith('/summary'))return route.fulfill({json:{businesses:1}});
    return route.fulfill({json:[]});
  });
  await page.goto('/platform-admin/login');
  await expect(page.getByRole('heading',{name:'Super Admin sign in'})).toBeVisible();
  await page.getByLabel('Email').fill('operator@example.com');
  await page.getByLabel('Password').fill(process.env.E2E_PASSWORD);
  await page.getByRole('button',{name:'Continue securely'}).click();
  await page.getByLabel('Six digit code').fill('123456');
  await page.getByRole('button',{name:'Verify and enter'}).click();
  await expect(page).toHaveURL(/\/platform-admin$/);
  expect(verified).toBeTruthy();
  expect(await page.evaluate(()=>Object.values(localStorage).join(' '))).not.toContain(process.env.E2E_PASSWORD);
});

test('usage insights edit finite quotas with stale update protection',async({page})=>{
  const writes=[];
  const limits={seats:5,leads:500,contacts:500,companies:250,deals:500,tasks:1000,storage_bytes:1073741824,workflow_executions:1000};
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    if(req.method()==='PUT'){writes.push(req.postDataJSON());return route.fulfill({json:{ok:true}});}
    const data=path.endsWith('/summary')?{businesses:1}:path.endsWith('/usage')?{history_note:'Recorded writes since instrumentation.',resources:{leads:{used:450,limit:500,remaining:50,percent:90}},trends:[{period:'2026-10-23',resource:'leads',created:2,updated:1,deleted:0,added_units:2,removed_units:0}]}:
      path.endsWith('/limits')?{limits,defaults_for_new_pilots:limits}:path.endsWith('/organizations/1')?{name:'Approved business',access_status:'active',verified_owners:[]}:
      path.endsWith('/usage-summary')?{owners:1,active_employee_seats:2,near_seat_limits:0,near_resource_limits:1,current_totals:{leads:450}}:[];
    await route.fulfill({json:data});
  });
  await page.goto('/platform-admin');
  await page.getByLabel('Organization ID').fill('1');
  await page.getByRole('button',{name:'View insights'}).click();
  await expect(page.getByText('90%',{exact:false})).toBeVisible();
  await page.getByRole('button',{name:'Edit this business’s limits'}).click();
  await page.getByRole('dialog').getByLabel('Leads').fill('2000');
  await page.getByLabel('Change reason').fill('Approved capacity increase');
  await page.getByRole('button',{name:'Save limits',exact:true}).click();
  await expect.poll(()=>writes.length).toBe(1);
  expect(writes[0]).toEqual({limits:{...limits,leads:2000},expected_limits:limits,reason:'Approved capacity increase'});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});
