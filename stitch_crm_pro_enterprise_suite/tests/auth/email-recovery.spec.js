import {test,expect} from '@playwright/test';

test.beforeEach(async({page})=>{
  await page.route('**/api/v1/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/auth/config'))return route.fulfill({json:{provider:'supabase',recovery_available:true,session_hours:8,remember_days:30,business_registration_enabled:false}});
    return route.fulfill({status:401,json:{detail:'Sign in required'}});
  });
});

test('expired provider link explains recovery and removes callback values',async({page})=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto('/login#error=access_denied&error_code=otp_expired&error_description=untrusted-message');
  await expect(page.locator('#login-error-banner')).toContainText('expired or has already been used');
  await expect(page.locator('#login-error-banner')).not.toContainText('untrusted-message');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('button',{name:'Forgot password?'})).toBeEnabled();
  expect(errors).toEqual([]);
});

test('new default-template code opens password form without exposing credentials',async({page})=>{
  const posts=[];
  await page.route('**/api/v1/auth/recovery/exchange',async route=>{
    posts.push(route.request().postDataJSON());
    await route.fulfill({json:{recovery:true}});
  });
  await page.route('**/api/v1/auth/password',async route=>{
    posts.push(route.request().postDataJSON());
    await route.fulfill({json:{message:'Password updated. Please sign in again.'}});
  });
  await page.goto('/login?code=synthetic-once-only-code');
  const dialog=page.getByRole('dialog');
  await expect(dialog.getByRole('heading',{name:'Set your password'})).toBeVisible();
  await expect(page).toHaveURL(/\/login$/);
  await dialog.getByLabel('New password').fill('SyntheticUserPassword!');
  await dialog.getByRole('button',{name:'Set password',exact:true}).click();
  await expect(page.locator('#login-error-banner')).toContainText('Password updated. Please sign in again.');
  expect(posts).toEqual([{code:'synthetic-once-only-code'},{password:'SyntheticUserPassword!'}]);
  expect(await page.evaluate(()=>Object.keys(localStorage).some(key=>/token|verifier/i.test(key)))).toBe(false);
});

test('callback from another browser fails without opening password form',async({page})=>{
  await page.route('**/api/v1/auth/recovery/exchange',route=>route.fulfill({status:400,json:{detail:'Request a new recovery email and open its link in the same browser.'}}));
  await page.goto('/login?code=unusable-code');
  await expect(page.locator('#login-error-banner')).toContainText('same browser');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page).toHaveURL(/\/login$/);
});

test('old implicit recovery tokens are cleared and never submitted as proof',async({page})=>{
  const writes=[];page.on('request',request=>{if(request.method()==='POST')writes.push(request.url());});
  await page.goto('/login#access_token=synthetic-private-token&refresh_token=synthetic-refresh&type=recovery');
  await expect(page.locator('#login-error-banner')).toContainText('Request a new recovery email');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page).toHaveURL(/\/login$/);
  expect(writes).toEqual([]);
});
