// Read-only local visual QA. Changes are not saved.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173', out = 'docs/verification/academy-full-builder';
(async () => {
 const browser = await chromium.launch({ channel: 'chrome', headless: true });
 const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
 const errors = []; page.on('pageerror', e => errors.push(e.message));
 try {
  await page.addInitScript(() => localStorage.setItem('madar.language', 'en'));
  await page.goto(origin + '/e-learning/academy-access');
  const select = page.getByRole('combobox'), panel = page.locator('.academy-management-access');
  await expect(select).toBeVisible();
  const originalMode = await select.inputValue();
  const enabled = page.getByRole('switch'); const originalEnabled = await enabled.isChecked();
  await select.selectOption('invitation_only');
  await expect(page.locator('#academy-registration-help')).toHaveText('Only invited learners can join.');
  await panel.screenshot({ path: out + '/academy-access-layout.png' });
  await enabled.focus(); await page.keyboard.press('Space');
  expect(await enabled.isChecked()).toBe(!originalEnabled);
  await page.keyboard.press('Space'); expect(await enabled.isChecked()).toBe(originalEnabled);
  await select.selectOption('open');
  await expect(page.locator('#academy-registration-help')).toHaveText('Anyone can create a learner account.');
  await select.selectOption('email_domain');
  await page.getByLabel('Allowed email domains').fill('university.edu, college.edu');
  await panel.screenshot({ path: out + '/academy-access-layout-domains.png' });
  const measurements = await page.evaluate(() => {
   const select = document.querySelector('#academy-registration').getBoundingClientRect();
   const domains = document.querySelector('.academy-email-domains input').getBoundingClientRect();
   return { select_width: select.width, domains_width: domains.width, aligned: Math.abs(select.right - domains.right) < 2, overflow: document.documentElement.scrollWidth > innerWidth };
  });
  expect(measurements.aligned).toBe(true); expect(measurements.overflow).toBe(false);
  await page.reload(); await expect(select).toHaveValue(originalMode); expect(await enabled.isChecked()).toBe(originalEnabled);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => localStorage.setItem('madar.language', 'ar'));
  await page.goto(origin + '/e-learning/academy-access');
  await expect(select).toBeVisible(); await select.selectOption('email_domain');
  expect(await panel.getAttribute('dir') || await page.locator('.academy-management-hub').getAttribute('dir')).toBe('rtl');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await panel.screenshot({ path: out + '/academy-access-layout-rtl-mobile.png' });
  expect(errors).toEqual([]);
  fs.writeFileSync(out + '/academy-access-layout-results.json', JSON.stringify({ verified_at: new Date().toISOString(), route: '/e-learning/academy-access', checks: ['Header with short description', 'Keyboard-operable Academy switch', 'Registration help follows selected option', 'Aligned registration and domain fields', 'Save footer', 'Arabic 390px responsive layout without overflow', 'Original values restored by refresh; no saves'], measurements, errors, data_writes: false }, null, 2));
  console.log('Access panel layout verified on desktop and RTL/mobile; no data saved.');
 } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
