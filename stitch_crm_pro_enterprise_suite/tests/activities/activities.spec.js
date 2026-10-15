import {test,expect} from '@playwright/test';
import {authenticate,api,company,lead,pipeline,unique,email,loginUI,collectPageErrors} from '../fixtures/live-api.js';

test('actual logged activity appears in the interaction feed',async({page})=>{await authenticate(page);const subject=unique('Discovery call');await page.goto('/tasks');await page.getByRole('button',{name:'Log Activity',exact:true}).click();await page.getByLabel('Subject',{exact:false}).fill(subject);await page.getByRole('button',{name:'Save Activity',exact:true}).click();await expect(page.locator('#activities-list')).toContainText(subject);await page.reload();await expect(page.locator('#activities-list')).toContainText(subject);});
