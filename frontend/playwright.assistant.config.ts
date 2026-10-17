import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir:'./tests', testMatch:'assistant*.spec.ts', fullyParallel:false, workers:1,
  timeout:45000, expect:{timeout:10000}, reporter:'list',
  outputDir:'../.runtime/assistant-browser',
  use:{baseURL:process.env.FRONTEND_URL||'http://127.0.0.1:4173',channel:'chrome',headless:true,serviceWorkers:'block',viewport:{width:1440,height:1000},screenshot:'only-on-failure',trace:'retain-on-failure'},
})
