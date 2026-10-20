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

for(const width of [1440,390])test(`admin layout and scoped membership review at ${width}px`,async({page})=>{
  await page.setViewportSize({width,height:950});const writes=[],errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.route('**/api/v1/**',async route=>{
    const r=route.request(),path=new URL(r.url()).pathname;
    if(r.method()==='PUT'){writes.push({path,body:r.postDataJSON()});return route.fulfill({json:{ok:true}});}
    const data=path.endsWith('/summary')?{businesses:1,active:1,suspended:0,expired:0,pending:0,active_users:2,occupied_seats:2,active_pilots:1,expiring_pilots:1}:
      path.endsWith('/organizations')?[{id:1,name:'Business A',slug:'a',is_suspended:false,access_status:'active',members:2,seat_limit:5,plan:'Free Pilot'}]:
      path.endsWith('/organizations/1')?{name:'Business A',created_at:'2026-10-16T00:00:00Z',access_status:'active',verified_owners:[{id:7,name:'Verified Owner',email:'owner@example.com'}]}:
      path.endsWith('/subscriptions/1')?{plan:{name:'Free Pilot'},subscription:{status:'active',ends_at:'2026-11-16T00:00:00Z'},seats:{active:2,pending:1,limit:5},entitlements:{analytics:true,exports:true,workflows:true,attachments:true}}:
      path.endsWith('/members')?[{user_id:7,name:'Employee',email:'member@example.com',role:'viewer',is_active:true,auth_linked:true}]:
      path.endsWith('/identity')?{verified:true}:
      path.endsWith('/invitations')?[{id:12,email:'invite@example.com',role:'viewer',expires_at:'2026-11-01T00:00:00Z'}]:[];
    return route.fulfill({json:data});
  });
  await page.goto('/platform-admin');
  await expect(page.getByText('Expiring within 7 days',{exact:true})).toBeVisible();
  await expect(page.getByRole('navigation')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:`test-results/platform-admin-${width}.png`,fullPage:true});
  await page.getByRole('button',{name:'Details',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Organization members',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Verify identity',exact:true}).click();
  await expect(page.getByText('Verified matching email',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Revoke access',exact:true}).click();
  await page.getByLabel('Revocation reason').fill('Explicit member access review');
  await page.getByRole('button',{name:'Confirm revocation',exact:true}).click();
  await expect.poll(()=>writes.length).toBe(1);
  expect(writes[0]).toEqual({path:'/api/v1/platform/organizations/1/members/7/revoke',body:{reason:'Explicit member access review'}});
  expect(errors).toEqual([]);
});

test('search filters requests and server errors stay in confirmation dialog',async({page})=>{
  const queries=[];
  await page.route('**/api/v1/**',async route=>{
    const r=route.request(),url=new URL(r.url()),path=url.pathname;
    if(r.method()==='PUT')return route.fulfill({status:409,json:{detail:'The final active owner cannot lose ownership or access'}});
    if(path.endsWith('/organizations'))queries.push(url.search);
    const data=path.endsWith('/summary')?{businesses:1}:path.endsWith('/organizations')?[{id:1,name:'Business A',slug:'a',is_suspended:false}]:[];
    return route.fulfill({json:data});
  });
  await page.goto('/platform-admin');
  await page.getByLabel('Business name').fill('Business A');await page.getByLabel('Status',{exact:true}).selectOption('expired');
  await page.getByRole('button',{name:'Search',exact:true}).click();
  await expect.poll(()=>queries.some(q=>q.includes('status=expired')&&q.includes('q=Business+A'))).toBeTruthy();
  await page.getByRole('button',{name:'Suspend',exact:true}).click();
  await page.getByLabel('Reason').fill('Review');await page.getByRole('button',{name:'Confirm',exact:true}).click();
  await expect(page.getByRole('dialog')).toContainText('The final active owner cannot lose ownership or access');
  await expect(page.getByRole('button',{name:'Confirm',exact:true})).toBeEnabled();
});
