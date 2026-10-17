/* Real application map/replay smoke. Run with Mongo, API and Vite running. */
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
let browser;
let page;
const evidence = { result: 'running', runtimeErrors: [], apiErrors: [], replay: [] };
const assert = (value, message) => { if (!value) throw new Error(message); };

(async () => {
  const base = process.env.FRONTEND_URL || 'http://127.0.0.1:5173';
  const deadline = Date.now() + 90000;
  while (true) {
    try { if ((await fetch(base + '/api/health', { signal: AbortSignal.timeout(3000) })).ok) break; } catch {}
    if (Date.now() > deadline) throw new Error('Application health check did not become ready');
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  browser = await chromium.launch({ channel: 'chrome', headless: true });
  page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(60000);
  page.on('pageerror', error => { evidence.runtimeErrors.push(error.message); console.error('Browser error:', error.message); });
  page.on('requestfailed', request => console.error('Request failed:', new URL(request.url()).pathname, request.failure()?.errorText));
  page.on('response', response => {
    if (response.url().includes('/api/') && response.status() >= 400)
      evidence.apiErrors.push({ path: new URL(response.url()).pathname, status: response.status() });
  });
  await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.getByRole('button', { name: 'District admin', exact: true }).click();
  console.log('Admin authenticated; opening outbreak map');
  const [statusResponse, initialMapResponse] = await Promise.all([
    page.waitForResponse(response => response.url().endsWith('/api/demo/status') && response.ok()),
    page.waitForResponse(response => response.url().includes('/api/outbreaks/map') && response.ok()),
    page.getByRole('link', { name: 'Outbreak map', exact: true }).click(),
  ]);
  const initialMap = await initialMapResponse.json();
  let status = await statusResponse.json();
  evidence.initial = { reports: initialMap.total_cases, clusters: initialMap.clusters.length, completed: status.completed };
  assert(status.enabled, 'Demo must be enabled for this local smoke test');
  await expect(page.locator('.surveillance-map')).toBeVisible();

  while (status.completed < status.total) {
    console.log(`Replaying observation ${status.completed + 1} / ${status.total}`);
    const replayResponse = page.waitForResponse(response => response.url().endsWith('/api/demo/replay') && response.request().method() === 'POST');
    await page.getByRole('button', { name: 'Replay next report', exact: true }).click();
    const response = await replayResponse;
    assert(response.ok(), `Replay returned HTTP ${response.status()}`);
    const previous = status.completed;
    status = await response.json();
    assert(status.completed === previous + 1, 'Replay failed to advance by exactly one report');
    assert(status.new_case_ids.length === 1, 'Replay must persist exactly one new scenario observation');
    for (const cluster of status.clusters) {
      assert(cluster.factors.reduce((sum, factor) => sum + factor.points, 0) === cluster.score, 'Cluster score differs from its actual factor total');
      assert(cluster.status !== 'confirmed_outbreak', 'Synthetic replay must not officially confirm an outbreak');
    }
    evidence.replay.push({ completed: status.completed, cases: status.new_case_ids, clusters: status.clusters.map(cluster => ({ score: cluster.score, status: cluster.status, animals: cluster.animal_count })) });
    await expect(page.locator('.demo-replay-actions strong')).toHaveText(`${status.completed} / ${status.total}`);
  }

  const refreshResponse = page.waitForResponse(response => response.url().includes('/api/outbreaks/map') && response.ok());
  await page.getByRole('button', { name: 'Refresh map', exact: true }).click();
  const finalMap = await (await refreshResponse).json();
  assert(finalMap.clusters.length > 0, 'Completed replay should produce a real calculated cluster');
  await expect(page.locator('.hotspot-row')).toHaveCount(finalMap.clusters.length);
  await page.locator('.hotspot-row').first().click();
  const selected = [...finalMap.clusters].sort((a, b) => b.score - a.score)[0];
  await expect(page.locator('.hotspot-details .risk-factor')).toHaveCount(selected.factors.length);
  await expect(page.locator('.hotspot-details .factor-total strong')).toHaveText(`${selected.score} / 100`);
  assert(finalMap.cases.every(item => item.location.type === 'Point' && item.location.coordinates.length === 2), 'Map observations must have GeoJSON coordinates');
  await expect(page.locator('.report-density-canvas')).toBeVisible();
  // Exercise zero-size resize followed by recovery, as happens during layout changes/unmount.
  await page.evaluate(async () => {
    const map = document.querySelector('.surveillance-map');
    map.style.width = '0px'; map.style.height = '0px'; window.dispatchEvent(new Event('resize'));
    await new Promise(resolve => setTimeout(resolve, 150));
    map.style.width = ''; map.style.height = ''; window.dispatchEvent(new Event('resize'));
  });
  await expect(page.locator('.report-density-canvas')).toBeVisible();
  assert(await page.locator('.leaflet-overlay-pane path').count() > 0, 'No report/cluster vector overlays rendered');

  await page.getByLabel('Group nearby markers', { exact: true }).uncheck();
  assert(await page.locator('.leaflet-overlay-pane path').count() >= finalMap.cases.length, 'Individual report markers failed to render');
  await page.getByLabel('Density layer', { exact: true }).uncheck();
  await expect(page.locator('.report-density-canvas')).toHaveCount(0);
  await page.getByLabel('Density layer', { exact: true }).check();
  await expect(page.locator('.report-density-canvas')).toBeVisible();

  await page.getByLabel('Suspected disease', { exact: true }).selectOption('fmd');
  const filterResponse = page.waitForResponse(response => response.url().includes('/api/outbreaks/map') && response.url().includes('disease=fmd') && response.ok());
  await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
  const filtered = await (await filterResponse).json();
  assert(filtered.cases.every(item => item.triage?.disease_code === 'fmd'), 'Disease filtering returned another disease');
  evidence.filter = { disease: 'fmd', matchingReports: filtered.total_cases };
  await page.getByLabel('Suspected disease', { exact: true }).selectOption('lsd');
  const restoreResponse = page.waitForResponse(response => response.url().includes('/api/outbreaks/map') && response.url().includes('disease=lsd') && response.ok());
  await page.getByRole('button', { name: 'Apply filters', exact: true }).click();
  await restoreResponse;
  await page.locator('.hotspot-row').first().click();
  fs.mkdirSync('.runtime/screenshots', { recursive: true });
  await page.screenshot({ path: '.runtime/screenshots/phase3-outbreak-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  assert(!(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)), 'Mobile map page has horizontal overflow');
  await page.screenshot({ path: '.runtime/screenshots/phase3-outbreak-mobile.png', fullPage: true });
  const tileFailureNotice = await page.locator('.map-tile-notice').count() > 0;
  await page.getByRole('button', { name: 'Sign out', exact: true }).click();
  await page.waitForURL('**/login');
  assert(!evidence.runtimeErrors.length, `Browser runtime errors: ${evidence.runtimeErrors.join('; ')}`);
  assert(!evidence.apiErrors.length, `API failures: ${JSON.stringify(evidence.apiErrors)}`);
  Object.assign(evidence, { result: 'passed', desktop: '1440x1000', mobile: '390x844', final: { reports: finalMap.total_cases, clusters: finalMap.clusters.length, selectedScore: selected.score, factors: selected.factors.length }, tileFailureNotice });
  fs.writeFileSync('.runtime/phase3-browser.json', JSON.stringify(evidence, null, 2));
  console.log(JSON.stringify(evidence));
  await browser.close();
})().catch(async error => {
  evidence.result = 'failed'; evidence.error = error.message;
  fs.mkdirSync('.runtime/screenshots', { recursive: true });
  fs.writeFileSync('.runtime/phase3-browser.json', JSON.stringify(evidence, null, 2));
  console.error(error);
  if (page) {
    console.error((await page.locator('body').innerText()).slice(0, 5000));
    await page.screenshot({ path: '.runtime/screenshots/phase3-browser-failure.png', fullPage: true }).catch(() => {});
  }
  if (browser) await browser.close();
  process.exit(1);
});
