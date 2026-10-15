import {test,expect} from '@playwright/test';
import fs from 'node:fs/promises';
import {authenticate} from '../fixtures/live-api.js';

test('record a local performance baseline against the isolated real API',async({page},testInfo)=>{
  test.skip(testInfo.project.name!=='chromium','Development baseline runs once; it is not a hosted capacity test.');
  await authenticate(page);const begin=Date.now();await page.goto('/dashboard');
  await expect(page.locator('[data-kpi=total_leads]')).toBeVisible();await page.waitForLoadState('networkidle');
  const ready=Date.now()-begin;
  const navigation=await page.evaluate(()=>{const n=performance.getEntriesByType('navigation')[0];return {ttfb_ms:n.responseStart-n.requestStart,dom_content_loaded_ms:n.domContentLoadedEventEnd-n.startTime,transfer_bytes:n.transferSize};});
  const samples=[];let failures=0;const start=Date.now();
  for(let batch=0;batch<6;batch++)await Promise.all(Array.from({length:5},async()=>{const stamp=Date.now();const r=await page.request.get('/api/v1/companies?page_size=100');if(r.status()!==200)failures++;samples.push(Date.now()-stamp);}));
  samples.sort((a,b)=>a-b);const elapsed=Date.now()-start;
  const result={scope:'Local loopback, isolated SQLite API, legacy test authentication, five concurrent readers, empty CRM dataset. Not production capacity or provider latency.',dashboard_ready_ms:ready,navigation,api:{requests:30,concurrency:5,failures,median_ms:samples[Math.floor(samples.length/2)],p95_ms:samples[Math.ceil(samples.length*.95)-1],elapsed_ms:elapsed,requests_per_second:Number((30000/elapsed).toFixed(2))}};
  await fs.mkdir('../qa-results/implementation',{recursive:true});await fs.writeFile('../qa-results/implementation/local-performance.json',JSON.stringify(result,null,2));
  await testInfo.attach('local-performance.json',{body:JSON.stringify(result,null,2),contentType:'application/json'});
  expect(failures).toBe(0);
});
