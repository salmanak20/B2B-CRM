import {test,expect} from '@playwright/test';
import {loginUI} from '../fixtures/live-api.js';

test('team and shared API lists survive host trailing-slash normalization',async({page})=>{
  // Reproduce the preview host stripping slashes before FastAPI receives paths.
  await page.route('**/api/v1/**',route=>{
    const url=new URL(route.request().url());
    if(url.pathname.endsWith('/'))url.pathname=url.pathname.slice(0,-1);
    return route.continue({url:url.toString()});
  });
  await loginUI(page);
  for(const path of ['audit-logs','notifications','search?q=QA']){
    const response=await page.request.get('/api/v1/'+path,{maxRedirects:0});
    expect(response.status()).toBe(200);
    expect(response.headers().location).toBeUndefined();
  }
  await page.goto('/users');
  await expect(page.getByRole('heading',{name:'Team Management',exact:true})).toBeVisible();
  await expect(page.getByRole('heading',{name:'Pending invitations',exact:true})).toBeVisible();
  await expect(page.locator('main .error')).toHaveCount(0);
});
