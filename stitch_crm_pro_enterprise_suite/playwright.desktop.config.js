import {defineConfig,devices} from '@playwright/test';

export default defineConfig({
  testDir:'./tests/desktop',
  timeout:30000,
  expect:{timeout:7000},
  use:{...devices['Desktop Chrome'],channel:'chrome',baseURL:'http://127.0.0.1:4175',trace:'retain-on-failure',screenshot:'only-on-failure'},
  webServer:{
    command:'npm run preview -- --host 127.0.0.1 --port 4175 --strictPort',
    url:'http://127.0.0.1:4175/login.html',
    reuseExistingServer:false,
    timeout:30000,
  },
});
