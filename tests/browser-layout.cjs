const {chromium, expect}=require('../frontend/node_modules/@playwright/test');
const fs=require('node:fs');
const base=process.env.FRONTEND_URL||'http://127.0.0.1:4173';
let browser,page;
(async()=>{
 browser=await chromium.launch({channel:'chrome',headless:true});
 page=await browser.newPage();page.setDefaultTimeout(60000);
 const errors=[],checks=[];page.on('pageerror',e=>errors.push(e.message));
 fs.mkdirSync('.runtime/screenshots',{recursive:true});
 for(const role of ['Farmer','Field worker','Veterinarian','Laboratory','District admin']){
  await page.goto(base+'/login');await page.getByRole('button',{name:role,exact:true}).click();await page.waitForURL(base+'/');
  await expect(page.locator('.loading')).toHaveCount(0);
  for(const width of [390,1440]){
   await page.setViewportSize({width,height:1000});
   const measure=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('body *')].map(e=>({tag:e.tagName,cls:e.className,right:e.getBoundingClientRect().right,width:e.getBoundingClientRect().width,position:getComputedStyle(e).position,overflow:getComputedStyle(e).overflow})).filter(e=>e.right>innerWidth+1)}));
   checks.push({role,width,scrollWidth:measure.scrollWidth});
   await page.screenshot({path:'.runtime/screenshots/'+role.replaceAll(' ','-')+'-'+width+'.png',fullPage:true});
   if(measure.scrollWidth>width+1)throw new Error(JSON.stringify(measure,null,2));
  }
  await page.getByRole('button',{name:'Sign out',exact:true}).click();await page.waitForURL('**/login');
 }
 if(errors.length)throw new Error(errors.join('\n'));
 fs.writeFileSync('.runtime/layout-browser.json',JSON.stringify({result:'passed',checks,runtimeErrors:errors},null,2));console.log({result:'passed',checks,runtimeErrors:errors});await browser.close();
})().catch(async e=>{console.error(e);if(browser)await browser.close();process.exit(1)});
