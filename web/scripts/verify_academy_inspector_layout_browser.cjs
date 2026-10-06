// Read-only local Academy Inspector verification; no editing, saving or publishing.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173', out = 'docs/verification/academy-full-builder';
(async () => {
 const browser = await chromium.launch({ channel: 'chrome', headless: true });
 const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
 const errors = []; page.on('pageerror', e => errors.push(e.message));
 async function record(id) {
  return page.evaluate(async id => {
   const { apiFetch } = await import('/src/utils/apiClient.js');
   const response = await apiFetch('/api/builder/projects/' + id);
   if (!response.ok) throw Error('Project read failed: ' + response.status);
   return (await response.json()).project;
  }, id);
 }
 async function choose() {
  const layer = page.locator('.builder-inspector').getByRole('combobox', { name: 'Select an element', exact: true });
  await expect(layer).toBeVisible();
  const value = await layer.locator('option').evaluateAll(options => options.find(option => option.textContent.includes('Featured Courses'))?.value);
  expect(value).toBeTruthy(); await layer.selectOption(value);
  await expect(page.locator('.academy-content-inspector')).toBeVisible();
  await expect(page.locator('.academy-content-choice').first()).toBeVisible();
 }
 async function measure() {
  return page.locator('.academy-content-inspector').evaluate(node => ({
   border: getComputedStyle(node).borderTopWidth,
   nested_border: getComputedStyle(node.querySelector('.academy-content-choices')).borderTopWidth,
   rows: [...node.querySelectorAll('.academy-content-choice')].map(row => {
    const checkbox = row.querySelector('input'), title = row.querySelector('span');
    const a = checkbox.getBoundingClientRect(), b = title.getBoundingClientRect();
    return { width: a.width, height: a.height, display: getComputedStyle(row).display, aligned: Math.abs((a.top + a.bottom)/2 - (b.top + b.bottom)/2) < 2 };
   })
  }));
 }
 try {
  await page.addInitScript(() => localStorage.setItem('madar.language', 'en'));
  await page.goto(origin + '/e-learning/landing-page'); await choose();
  const route = new URL(page.url()).pathname, id = route.match(/projects\/([^/]+)/)[1];
  const before = await record(id), desktop = await measure();
  expect(desktop.border).toBe('0px'); expect(desktop.nested_border).toBe('0px');
  expect(desktop.rows.length).toBeGreaterThan(0);
  desktop.rows.forEach(row => { expect(row.width).toBe(17); expect(row.height).toBe(17); expect(row.display).toBe('flex'); expect(row.aligned).toBe(true); });
  await page.locator('.academy-content-inspector').screenshot({ path: out + '/academy-inspector-aligned-checkboxes.png' });
  await page.setViewportSize({ width: 1024, height: 1000 });
  await page.addInitScript(() => localStorage.setItem('madar.language', 'ar'));
  await page.goto(origin + route); await choose();
  await page.locator('.academy-content-inspector').evaluate(node => node.setAttribute('dir', 'rtl'));
  const tablet = await measure(); tablet.rows.forEach(row => { expect(row.width).toBe(17); expect(row.aligned).toBe(true); });
  await page.locator('.academy-content-inspector').screenshot({ path: out + '/academy-inspector-aligned-checkboxes-rtl-tablet.png' });
  const after = await record(id);
  expect(after.draft_schema).toEqual(before.draft_schema); expect(after.draft_revision).toBe(before.draft_revision);
  expect(errors).toEqual([]);
  fs.writeFileSync(out + '/academy-inspector-layout-results.json', JSON.stringify({ verified_at: new Date().toISOString(), route, desktop, tablet, rtl_check: 'Inspector dir attribute changed in browser only; native Builder remains English', checks: ['Academy content and nested selection borders removed', 'Native 17px Inspector checkbox rows align with names', 'Tablet RTL geometry', 'Saved draft and revision unchanged'], errors, data_writes: false }, null, 2));
  console.log('Academy Inspector borders and aligned checkboxes verified; saved draft unchanged.');
 } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
