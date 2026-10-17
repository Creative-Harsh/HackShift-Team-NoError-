/* Browser smoke: node tests/browser-smoke.cjs; requires frontend dev server and API. */
const { chromium } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
let activePage;
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage(); activePage = page;
  const errors = [];
  page.on('pageerror', error => { errors.push(error.message); console.error('Browser runtime:', error.message); });
  const base = process.env.FRONTEND_URL || 'http://127.0.0.1:5173';
  const readyDeadline = Date.now() + 90000;
  while (true) {
    try { if ((await fetch(base + '/api/health', { signal: AbortSignal.timeout(3000) })).ok) break; } catch {}
    if (Date.now() > readyDeadline) throw new Error('Local application did not become ready');
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  page.setDefaultTimeout(60000);
  await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.getByRole('button', { name: 'Farmer', exact: true }).click();
  await page.getByRole('link', { name: 'My animals', exact: true }).click();
  await page.getByRole('textbox', { name: '12-digit Pashu Aadhaar' }).fill('261280000001');
  await page.getByRole('button', { name: 'Find record', exact: true }).click();
  await page.waitForURL('**/animals/demo-animal-01');
  await page.getByRole('link', { name: 'Report symptoms', exact: true }).first().click();
  await page.waitForURL(url => url.pathname === '/report');
  await page.locator('select[name=animal_id]').selectOption('demo-animal-01');
  await page.getByLabel('Skin lesions / nodules').check();
  await page.getByLabel('Swelling').check();
  await page.getByLabel('Fever', { exact: false }).check();
  await page.getByLabel('Temperature (°C)', { exact: true }).fill('40.2');
  await page.getByLabel('Vaccination status', { exact: true }).selectOption('overdue');
  const responsePromise = page.waitForResponse(r => r.url().endsWith('/api/reports') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Submit health report', exact: true }).click();
  const caseData = await (await responsePromise).json();
  if (!caseData.triage || !caseData.risk || caseData.risk.factors.reduce((s, f) => s + f.points, 0) !== caseData.risk.score) throw new Error('Report lacks a consistent backend assessment');
  await page.waitForURL('**/cases/**');
  await page.getByRole('heading', { name: 'Preliminary assessment', exact: true }).waitFor();
  await page.getByRole('heading', { name: 'Explainable risk score', exact: true }).waitFor();
  await page.getByRole('meter', { name: 'Risk score' }).waitFor();
  const casePath = new URL(page.url()).pathname;
  fs.mkdirSync('.runtime/screenshots', { recursive: true });
  await page.screenshot({ path: '.runtime/screenshots/phase2-case-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
  if (overflow) throw new Error('Mobile page has horizontal overflow');
  await page.screenshot({ path: '.runtime/screenshots/phase2-case-mobile.png', fullPage: true });
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await page.waitForURL('**/login');
  if (errors.length) throw new Error(errors.join('\n'));
  const summary = { result: 'passed', casePath, desktop: '1440x1000', mobile: '390x844', runtimeErrors: errors.length, riskScore: caseData.risk.score, suspectedDisease: caseData.triage.suspected_disease };
  fs.writeFileSync('.runtime/phase2-browser.json', JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary));
  await browser.close();
})().catch(async error => { console.error(error); if (activePage) { console.error((await activePage.locator('body').innerText()).slice(0,4000)); fs.mkdirSync('.runtime/screenshots', { recursive:true }); await activePage.screenshot({ path:'.runtime/screenshots/browser-failure.png', fullPage:true }).catch(()=>{}); } process.exit(1); });



