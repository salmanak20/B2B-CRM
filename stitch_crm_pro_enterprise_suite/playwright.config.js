import {defineConfig,devices} from '@playwright/test';
import {randomBytes} from 'node:crypto';
process.env.E2E_PASSWORD ||= 'QA-'+randomBytes(24).toString('base64url');
process.env.CRM_TEST_RUN='1';
process.env.API_BACKEND_ORIGIN='http://127.0.0.1:8001';
export default defineConfig({testDir:'./tests',timeout:60000,expect:{timeout:7000},fullyParallel:false,workers:1,retries:0,
  reporter:[['list'],['html',{outputFolder:'playwright-report',open:'never'}],['json',{outputFile:'test-results/playwright-results.json'}]],
  use:{baseURL:'http://127.0.0.1:5174',actionTimeout:10000,navigationTimeout:15000,trace:'retain-on-failure',screenshot:'only-on-failure',video:'retain-on-failure'},
  webServer:[{command:'..\\backend\\.venv\\Scripts\\python.exe ..\\backend\\tests\\browser_server.py',url:'http://127.0.0.1:8001/api/v1/health',reuseExistingServer:false,timeout:120000},
    {command:'npm.cmd run dev -- --host 127.0.0.1 --port 5174 --strictPort',url:'http://127.0.0.1:5174',reuseExistingServer:false,timeout:120000}],
  projects:[{name:'chromium',use:{...devices['Desktop Chrome'],channel:'chrome'}},{name:'firefox',use:{...devices['Desktop Firefox']}},{name:'webkit',use:{...devices['Desktop Safari']}},{name:'mobile-chromium',use:{...devices['Pixel 7'],channel:'chrome'}}]
});
