import {test,expect} from '@playwright/test';
import {authenticate,api,company,lead,pipeline,unique,email,loginUI,collectPageErrors} from '../fixtures/live-api.js';

test('protected pages redirect unauthenticated visitors',async({page})=>{await page.goto('/companies');await expect(page).toHaveURL(/\/login/);});
test('an active cookie session redirects away from login',async({page})=>{await authenticate(page);await page.goto('/login');await expect(page).toHaveURL(/\/dashboard$/);});
test('viewer cannot administer users or mutate customer records',async({page})=>{await authenticate(page,'viewer');await page.goto('/users');await expect(page.getByRole('alert')).toContainText('Administrator access');const r=await page.request.post('/api/v1/companies',{data:{name:unique('Forbidden')}});expect(r.status()).toBe(403);await page.goto('/tasks');await expect(page.getByRole('button',{name:'Add Task',exact:true})).toHaveCount(0);});
