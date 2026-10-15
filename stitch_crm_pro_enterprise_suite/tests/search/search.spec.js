import {test,expect} from '@playwright/test';
import {authenticate,api,company,lead,pipeline,unique,email,loginUI,collectPageErrors} from '../fixtures/live-api.js';

test('visible global search queries real records and supports result navigation',async({page})=>{await authenticate(page);const c=await company(page);await page.goto('/companies');await page.locator('[data-global-search]').fill(c.name);const dropdown=page.locator('.global-search-dropdown');await expect(dropdown).toContainText(c.name);await dropdown.getByRole('link',{name:c.name,exact:true}).click();await expect(page.getByRole('heading',{name:c.name,exact:true})).toBeVisible();});
