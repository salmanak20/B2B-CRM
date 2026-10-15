import {test,expect} from '@playwright/test';
import {authenticate,api,company,lead,pipeline,unique,email,loginUI,collectPageErrors} from '../fixtures/live-api.js';

test('actual analytics render and reject reversed date ranges',async({page})=>{await authenticate(page);await page.goto('/reports');await expect(page.locator('[data-section=sales-performance]')).toContainText('Won revenue');await expect(page.locator('[data-section=lead-analytics]')).not.toContainText('[object Object]');await page.locator('#start-date').fill('2026-10-20');await page.locator('#end-date').fill('2026-10-01');await page.getByRole('button',{name:'Apply dates',exact:true}).click();await expect(page.getByRole('alert')).toContainText('Start date');});
