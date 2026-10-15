import {test,expect} from '@playwright/test';
import {authenticate,api,company,lead,pipeline,unique,email,loginUI,collectPageErrors} from '../fixtures/live-api.js';

test('actual lead CSV downloads permitted database records',async({page})=>{await authenticate(page);const record=await lead(page);await page.goto('/leads');const pending=page.waitForEvent('download');await page.getByRole('button',{name:'Export CSV',exact:true}).click();const download=await pending;const stream=await download.createReadStream();let text='';for await(const chunk of stream)text+=chunk.toString();expect(text).toContain(record.title);});
