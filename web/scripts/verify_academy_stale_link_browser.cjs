// Local-only verification of the reported stale bookmark. No fixtures or uploads.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173';
const output = 'docs/verification/academy-full-builder';
const stalePath = '/page-builder/projects/e0b6437a-d708-42c0-9efa-04b6639ddb18/pages/sections';

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => localStorage.setItem('madar.language', 'en'));
  try {
    await page.goto(origin + stalePath);
    await expect(page.getByRole('heading', { name: 'This project link is unavailable' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Open Academy Builder' })).toBeVisible();
    await expect(page).toHaveURL(origin + stalePath);
    await page.screenshot({ path: output + '/stale-link-recovery.png', fullPage: true });
    await page.getByRole('button', { name: 'Open Academy Builder' }).click();
    await expect(page).toHaveURL(/\/page-builder\/projects\/[^/]+\/pages$/);
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    const editor = new URL(page.url()).pathname;
    expect(editor).not.toContain('e0b6437a-d708-42c0-9efa-04b6639ddb18');
    await page.reload();
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    await expect(page).toHaveURL(origin + editor);
    await page.screenshot({ path: output + '/stale-link-opened-builder.png', fullPage: true });
    await page.goto(origin + '/e-learning/settings/academy');
    await page.getByRole('button', { name: 'Edit Academy', exact: true }).click();
    await expect(page).toHaveURL(origin + editor);
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => localStorage.setItem('madar.language', 'ar'));
    await page.goto(origin + stalePath);
    await expect(page.getByRole('button', { name: 'فتح منشئ الأكاديمية' })).toBeVisible();
    expect(await page.locator('.builder-project-loading').getAttribute('dir')).toBe('rtl');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: output + '/stale-link-rtl-mobile.png', fullPage: true });
    expect(errors).toEqual([]);
    fs.writeFileSync(output + '/stale-link-results.json', JSON.stringify({
      verified_at: new Date().toISOString(), origin, stalePath, editor,
      checks: ['Explicit recovery from exact reported URL', 'Current durable Academy draft reused', 'Reload persistence', 'Normal Academy hub Edit opens same project', 'RTL mobile recovery without horizontal overflow'], errors,
    }, null, 2));
    console.log('Stale Academy link recovery verified:', editor);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
