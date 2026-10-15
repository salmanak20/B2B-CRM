import {test,expect} from '@playwright/test';
import {createRequire} from 'node:module';
import {authenticate} from '../fixtures/live-api.js';
const require=createRequire(import.meta.url);
test('major pages have no serious WCAG findings and fit their viewport',async({page},testInfo)=>{
  test.setTimeout(120000);await authenticate(page);const findings=[];const errors=[];page.on('pageerror',e=>errors.push(e.message));
  for(const route of ['/dashboard','/companies','/contacts','/leads','/deals','/tasks','/calendar','/notifications','/settings','/users','/automations','/reports','/team']){
    await page.goto(route);await expect(page.locator('main h1')).toBeVisible();await page.waitForLoadState('networkidle');await page.addScriptTag({path:require.resolve('axe-core/axe.min.js')});
    const violations=await page.evaluate(async()=>{const result=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa']}});return result.violations.filter(v=>v.impact==='critical'||v.impact==='serious').map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}));});
    const width=await page.evaluate(()=>({viewport:innerWidth,document:document.documentElement.scrollWidth}));findings.push({route,violations,width});
  }
  await testInfo.attach('accessibility-and-layout.json',{body:JSON.stringify(findings,null,2),contentType:'application/json'});
  expect(findings.filter(p=>p.violations.length)).toEqual([]);expect(findings.filter(p=>p.width.document>p.width.viewport+2)).toEqual([]);expect(errors).toEqual([]);
});
test('native dialog supports focus and Escape dismissal',async({page})=>{await authenticate(page);await page.goto('/companies');await page.getByRole('button',{name:'Add Company',exact:true}).click();await expect(page.getByRole('dialog')).toBeVisible();await expect(page.locator('#company-name')).toBeFocused();await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);await expect(page.getByRole('button',{name:'Add Company',exact:true})).toBeFocused();});
