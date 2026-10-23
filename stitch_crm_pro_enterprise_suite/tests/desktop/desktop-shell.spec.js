import {test,expect} from '@playwright/test';

test('packaged business and platform sign-in routes navigate between static pages',async({page})=>{
  await page.route('https://b2-b-crm.vercel.app/api/v1/**',route=>route.fulfill({status:503,contentType:'application/json',body:'{"detail":"test service unavailable"}'}));
  await page.goto('/platform-admin/login.html');
  await expect(page.getByRole('heading',{name:'Super Admin sign in'})).toBeVisible();
  await page.getByRole('link',{name:'Business workspace sign in'}).click();
  await expect(page).toHaveURL(/\/login\.html$/);
  await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();
});

test('desktop shows a retry state when the network is unavailable',async({page,context})=>{
  await page.route('https://b2-b-crm.vercel.app/api/v1/**',route=>route.fulfill({status:503,contentType:'application/json',body:'{"detail":"test service unavailable"}'}));
  await page.goto('/login.html');
  await expect(page.getByRole('heading',{name:'Welcome back'})).toBeVisible();
  await context.setOffline(true);
  const status=page.getByRole('status').filter({hasText:'Internet connection lost'});
  await expect(status).toBeVisible();
  await expect(status.getByRole('button',{name:'Retry'})).toBeVisible();
});
