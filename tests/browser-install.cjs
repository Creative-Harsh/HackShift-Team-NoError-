// A persistent profile is required: Chrome intentionally disallows PWA install in incognito contexts.
const {chromium}=require('../frontend/node_modules/@playwright/test');
const fs=require('node:fs');
const path=require('node:path');
let context;
(async()=>{
 fs.mkdirSync('.runtime',{recursive:true});
 const profile=fs.mkdtempSync(path.resolve('.runtime/install-profile-'));
 context=await chromium.launchPersistentContext(profile,{channel:'chrome',headless:true});
 const page=await context.newPage();
 await page.goto((process.env.FRONTEND_URL||'http://127.0.0.1:4173')+'/login');
 await page.evaluate(async()=>{await navigator.serviceWorker.ready});
 const cdp=await context.newCDPSession(page);
 const result=await cdp.send('Page.getInstallabilityErrors');
 if(result.installabilityErrors.length)throw new Error(JSON.stringify(result));
 fs.writeFileSync('.runtime/install-browser.json',JSON.stringify({result:'passed',...result},null,2));
 console.log({result:'passed',...result});await context.close();
})().catch(async e=>{console.error(e);if(context)await context.close();process.exit(1)});
