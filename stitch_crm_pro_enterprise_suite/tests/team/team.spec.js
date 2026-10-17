import {test,expect} from '@playwright/test';

test('organization team controls preserve design and send scoped requests',async({page})=>{
  const writes=[];
  const profile={id:1,name:'Owner',email:'owner@example.com',role:{id:1,name:'admin'},organization_role:'owner',is_active:true,preferences:{}};
  await page.route('**/api/v1/**',async route=>{
    const request=route.request(),path=new URL(request.url()).pathname;
    if(request.method()!=='GET'){writes.push({path,body:request.postDataJSON()});return route.fulfill({json:{ok:true}});}
    const data={
      '/api/v1/auth/me':profile,'/api/v1/workspace':{name:'Legacy Organization',timezone:'UTC',currency:'USD'},
      '/api/v1/notifications/':[],'/api/v1/audit-logs/':[],
      '/api/v1/team/members':{actor_role:'owner',roles:['owner','admin','sales_manager','sales_rep','viewer'],members:[
        {user_id:1,name:'Owner',email:'owner@example.com',role:'owner',is_active:true,is_self:true,can_manage:true},
        {user_id:2,name:'Representative',email:'rep@example.com',role:'sales_rep',is_active:true,can_manage:true}]},
      '/api/v1/team/invitations':[{id:5,name:'Invited Employee',email:'new@example.com',role:'viewer',expires_at:'2026-10-23T12:00:00Z'}]
    }[path];
    await route.fulfill({json:data??[]});
  });
  await page.goto('/users');
  await expect(page.getByRole('heading',{name:'Team Management'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Pending invitations'})).toBeVisible();
  await page.getByRole('button',{name:'Invite Employee',exact:true}).click();
  await page.getByLabel('Full Name').fill('New Employee');
  await page.getByLabel('Email').fill('new@example.com');
  await page.getByLabel('Organization Role').selectOption('viewer');
  await page.getByRole('button',{name:'Send Invitation',exact:true}).click();
  await expect.poll(()=>writes.length).toBe(1);
  expect(writes[0]).toEqual({path:'/api/v1/team/invitations',body:{name:'New Employee',email:'new@example.com',role:'viewer'}});
  await page.locator('[data-member-edit="2"]').click();
  await page.getByLabel('Organization Role').selectOption('sales_manager');
  await page.getByRole('button',{name:'Save Access',exact:true}).click();
  await expect.poll(()=>writes.length).toBe(2);
  expect(writes[1].body).toEqual({role:'sales_manager',is_active:true});
});

test('administrator UI cannot offer owner promotion',async({page})=>{
  await page.route('**/api/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    const data=path.endsWith('/auth/me')?{id:1,name:'Admin',email:'admin@example.com',role:{id:1,name:'admin'},organization_role:'admin',preferences:{}}:
      path.endsWith('/workspace')?{name:'Workspace',timezone:'UTC',currency:'USD'}:
      path.endsWith('/team/members')?{actor_role:'admin',roles:['admin','sales_manager','sales_rep','viewer'],members:[{user_id:2,name:'Owner',email:'owner@example.com',role:'owner',is_active:true,can_manage:false}]}:[];
    await route.fulfill({json:data});
  });
  await page.goto('/users');
  await expect(page.getByText('Owner-controlled')).toBeVisible();
  await page.getByRole('button',{name:'Invite Employee',exact:true}).click();
  await expect(page.getByLabel('Organization Role').locator('option[value="owner"]')).toHaveCount(0);
});

test('verified recipient accepts pending invitation before choosing organization',async({page})=>{
  const writes=[];
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    if(req.method()==='POST'){
      writes.push({path,body:req.postDataJSON()});
      return route.fulfill({json:{organization_id:2}});
    }
    const data=path.endsWith('/auth/config')?{provider:'supabase',recovery_available:true,session_hours:8,remember_days:30}:
      path.endsWith('/auth/invitations')?[{id:8,organization_name:'Invited Organization',role:'sales_rep'}]:[];
    await route.fulfill({json:data});
  });
  await page.goto('/login');
  await expect(page.getByRole('heading',{name:'Organization invitations'})).toBeVisible();
  await page.getByRole('button',{name:'Accept Invitation',exact:true}).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  expect(writes.slice(0,2)).toEqual([{path:'/api/v1/auth/invitations/8/accept',body:{}},{path:'/api/v1/auth/organization',body:{organization_id:2}}]);
});
