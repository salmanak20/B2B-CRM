import {test,expect} from '@playwright/test';
import {authenticate,api,company,lead,pipeline,unique,email,loginUI,collectPageErrors} from '../fixtures/live-api.js';

test('logout revokes browser session and returns to login',async({page})=>{await authenticate(page);await page.goto('/dashboard');await page.getByRole('button',{name:'Sign out',exact:true}).click();await expect(page).toHaveURL(/\/login$/);expect((await page.request.get('/api/v1/auth/me')).status()).toBe(401);});
