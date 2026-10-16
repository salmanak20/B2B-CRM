import {test,expect} from '@playwright/test';

const config={provider:'supabase',recovery_available:true,session_hours:8,remember_days:30,business_registration_enabled:true};
const owner={id:3,name:'Business Owner',email:'owner@example.com',organization_id:3,organization_role:'owner',role:{id:1,name:'admin'},preferences:{}};

test('registration waits for email verification without activating a workspace',async({page})=>{
  const writes=[];
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    if(path.endsWith('/auth/config'))return route.fulfill({json:config});
    if(path.endsWith('/auth/business-signup')){writes.push(req.postDataJSON());return route.fulfill({json:{message:'Check your email to verify your account, then sign in.'}});}
    return route.fulfill({status:401,json:{detail:'Sign in required'}});
  });
  await page.goto('/login');
  await page.getByRole('button',{name:'Register business account'}).click();
  await page.getByLabel('Full name').fill('New Owner');
  const dialog=page.getByRole('dialog');
  await dialog.getByLabel('Email').fill('new@example.com');
  await dialog.getByLabel('Password').fill('secure-password-123');
  await dialog.getByRole('button',{name:'Register',exact:true}).click();
  await expect(page.getByRole('status')).toContainText('Check your email');
  expect(writes).toEqual([{name:'New Owner',email:'new@example.com',password:'secure-password-123'}]);
  await expect(page).toHaveURL(/\/login$/);
});

test('verified signup provisions an empty private workspace and retries with the same key',async({page},testInfo)=>{
  const writes=[];let created=false;
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    if(path.endsWith('/auth/onboarding')&&req.method()==='POST'){
      writes.push(req.postDataJSON());
      if(writes.length===1)return route.fulfill({status:503,json:{detail:'Please retry'}});
      created=true;return route.fulfill({json:{organization_id:3}});
    }
    const data=path.endsWith('/auth/config')?config:path.endsWith('/auth/recovery/verify')?{recovery:false}:
      path.endsWith('/auth/invitations')?[]:path.endsWith('/auth/organizations')?(created?[{id:3,name:'Business A'}]:[]):
      path.endsWith('/auth/onboarding')?{can_create:true}:path.endsWith('/auth/me')?owner:
      path.endsWith('/workspace')?{name:'Business A',timezone:'UTC',currency:'USD'}:[];
    return route.fulfill({json:data});
  });
  await page.goto('/login?token_hash=verified-test&type=signup');
  await expect(page.getByRole('heading',{name:'Create your business workspace'})).toBeVisible();
  await page.screenshot({path:testInfo.outputPath('onboarding.png'),fullPage:true});
  await page.getByLabel('Business name').fill('Business A');
  await page.getByRole('button',{name:'Create Workspace',exact:true}).click();
  await expect(page.getByRole('dialog').locator('[data-form-error]')).toContainText('Please retry');
  await page.getByRole('button',{name:'Create Workspace',exact:true}).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  expect(writes.length).toBe(2);expect(writes[0]).toEqual(writes[1]);
  expect(writes[0].name).toBe('Business A');expect(writes[0].request_key).toMatch(/^[a-f0-9-]{36}$/);
});

test('workspace selector verifies switches on the server and restores failed selection',async({page})=>{
  const switches=[];
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    if(path.endsWith('/auth/organization')){switches.push(req.postDataJSON());return route.fulfill({status:403,json:{detail:'Membership revoked'}});}
    const data=path.endsWith('/auth/config')?config:path.endsWith('/auth/me')?owner:
      path.endsWith('/auth/organizations')?[{id:3,name:'Business A'},{id:4,name:'Business B'}]:
      path.endsWith('/workspace')?{name:'Business A',timezone:'UTC',currency:'USD'}:[];
    await route.fulfill({json:data});
  });
  await page.goto('/settings');
  if(page.viewportSize().width<768)await page.getByRole('button',{name:'Open navigation'}).click();
  const selector=page.getByRole('combobox',{name:'Active workspace'});
  await expect(selector).toHaveValue('3');
  await selector.selectOption('4');
  await expect(selector).toBeEnabled();await expect(selector).toHaveValue('3');
  expect(switches).toEqual([{organization_id:4}]);
});

test('disabled registration leaves existing login unchanged',async({page})=>{
  const posts=[];
  await page.route('**/api/v1/**',async route=>{
    const req=route.request(),path=new URL(req.url()).pathname;
    if(req.method()==='POST'){posts.push(path);return route.fulfill({json:path.endsWith('/auth/login')?{user:owner}:{organization_id:3}});}
    if(path.endsWith('/auth/invitations')&&posts.length===0)return route.fulfill({status:401,json:{detail:'Sign in required'}});
    const data=path.endsWith('/auth/config')?{...config,business_registration_enabled:false}:
      path.endsWith('/auth/organizations')?[{id:3,name:'Existing Business'}]:path.endsWith('/auth/me')?owner:
      path.endsWith('/workspace')?{name:'Existing Business',timezone:'UTC',currency:'USD'}:[];
    await route.fulfill({json:data});
  });
  await page.goto('/login');
  await expect(page.getByRole('button',{name:'Register business account'})).toHaveCount(0);
  await page.locator('#email').fill('owner@example.com');
  await page.locator('#password').fill('secure-password-123');
  await page.getByRole('button',{name:'Sign In',exact:true}).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  expect(posts).toEqual(['/api/v1/auth/login','/api/v1/auth/organization']);
});
