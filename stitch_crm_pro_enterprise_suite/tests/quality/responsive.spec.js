import {test,expect} from '@playwright/test';
import {authenticate} from '../fixtures/live-api.js';
test('major layouts and forms work at desktop laptop tablet and phone widths',async({page},testInfo)=>{
  test.skip(testInfo.project.name!=='chromium','Width sweep is exercised in Chromium; other engines retain their project viewport checks.');test.setTimeout(120000);await authenticate(page);const results=[];
  for(const width of [1440,1024,768,375,430]){await page.setViewportSize({width,height:960});for(const route of ['/dashboard','/companies','/contacts','/leads','/deals','/tasks','/settings','/users','/automations','/calendar']){await page.goto(route);await expect(page.locator('main h1')).toBeVisible();const dimension=await page.evaluate(()=>({viewport:innerWidth,body:document.documentElement.scrollWidth}));results.push({route,...dimension});}
    await page.goto('/companies');await page.getByRole('button',{name:'Add Company',exact:true}).click();await expect(page.getByRole('dialog')).toBeVisible();const dimension=await page.evaluate(()=>{const r=document.querySelector('dialog').getBoundingClientRect();return {left:r.left,right:r.right,width:innerWidth};});expect(dimension.left).toBeGreaterThanOrEqual(0);expect(dimension.right).toBeLessThanOrEqual(dimension.width);await page.keyboard.press('Escape');
    if([1440,375].includes(width)){await page.goto('/dashboard');await page.waitForLoadState('networkidle');await page.screenshot({path:testInfo.outputPath('dashboard-'+width+'.png'),fullPage:true});}
  }
  await testInfo.attach('responsive-width-sweep.json',{body:JSON.stringify(results,null,2),contentType:'application/json'});expect(results.filter(r=>r.body>r.viewport+2)).toEqual([]);
});
