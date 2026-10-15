import {test,expect} from '@playwright/test';
import {authenticate,api,company,lead,pipeline,unique,email,loginUI,collectPageErrors} from '../fixtures/live-api.js';

test('dashboard KPIs match real stored database summaries',async({page})=>{await authenticate(page);await page.goto('/dashboard');await expect(page.locator('[data-kpi=total_companies]')).toBeVisible();const summary=await api(page,'GET','/dashboard/summary');await expect(page.locator('[data-kpi=total_companies]')).toHaveText(Number(summary.total_companies).toLocaleString());await expect(page.locator('[data-kpi=total_leads]')).toHaveText(Number(summary.total_leads).toLocaleString());expect(await page.locator('main').innerText()).not.toContain('[object Object]');});
