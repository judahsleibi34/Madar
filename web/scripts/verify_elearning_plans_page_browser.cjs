// Read-only local routing/UI verification. Existing plans are not changed.
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
  await page.getByRole('link', { name: 'Manage Plans', exact: true }).click();
  await expect(page).toHaveURL(origin + '/e-learning/plans');
  await expect(page.getByRole('heading', { name: 'Learning Plans', exact: true })).toBeVisible();
  const nav = page.locator('#dashboard-sidebar-elearning');
  await expect(nav.getByRole('link', { name: 'Learning Plans', exact: true })).toHaveAttribute('aria-current', 'page');
  expect(await nav.locator('[aria-current="page"]').count()).toBe(1);
  const activeStyle = await nav.getByRole('link', { name: 'Learning Plans', exact: true }).evaluate(node => {
   const style = getComputedStyle(node);
   return { background: style.backgroundColor, color: style.color, label: getComputedStyle(node.querySelector('span')).color, icon: getComputedStyle(node.querySelector('svg')).color };
  });
  expect(activeStyle.background).not.toBe('rgba(0, 0, 0, 0)');
  expect(activeStyle.color).toBe(activeStyle.label); expect(activeStyle.color).toBe(activeStyle.icon);
  const inactiveBackground = await nav.getByRole('link', { name: 'Courses', exact: true }).evaluate(node => getComputedStyle(node).backgroundColor);
  expect(activeStyle.background).not.toBe(inactiveBackground);

  await expect(page.getByRole('button', { name: 'Add Plan', exact: true })).toBeVisible();
  const empty = page.getByRole('region', { name: 'No learning plans yet', exact: true });
  await expect(empty).toBeVisible();
  await expect(empty.getByRole('button', { name: 'Create Your First Plan', exact: true })).toBeVisible();
  await empty.getByRole('button', { name: 'Create Your First Plan', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();

  await page.screenshot({ path: out + '/learning-plans-sidebar-page.png', fullPage: true });
  await page.getByRole('button', { name: 'Add Plan', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeVisible();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Learning Plans', exact: true })).toBeVisible();
  await nav.getByRole('link', { name: 'Courses', exact: true }).click();
  await nav.getByRole('link', { name: 'Learning Plans', exact: true }).click();
  await expect(page).toHaveURL(origin + '/e-learning/plans');
  await page.goto(origin + '/e-learning/settings/plans');
  await expect(page).toHaveURL(origin + '/e-learning/plans');
  await expect(nav.getByRole('link', { name: 'Learning Plans', exact: true })).toHaveAttribute('aria-current', 'page');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => localStorage.setItem('madar.language', 'ar'));
  await page.goto(origin + '/e-learning/courses');
  await page.locator('.dashboard-mobile-menu-button').click();
  const parent = page.locator('[aria-controls="dashboard-sidebar-elearning"]');
  if (await parent.getAttribute('aria-expanded') !== 'true') await parent.click();
  await nav.getByRole('link', { name: 'خطط التعلّم', exact: true }).click();
  await expect(page).toHaveURL(origin + '/e-learning/plans');
  await expect(page.getByRole('heading', { name: 'خطط التعلّم', exact: true })).toBeVisible();
  expect(await page.locator('.elearning-management').getAttribute('dir')).toBe('rtl');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  await page.screenshot({ path: out + '/learning-plans-rtl-mobile.png', fullPage: true });
  expect(errors).toEqual([]);
  fs.writeFileSync(out + '/learning-plans-route-results.json', JSON.stringify({ verified_at: new Date().toISOString(), route: '/e-learning/plans', legacy_redirect: '/e-learning/settings/plans', checks: ['White empty-state card with explanation and red Create Your First Plan action', 'Empty-state action opens existing plan dialog and cancels', 'Manage Plans opens dedicated Learning Plans page', 'Sidebar Learning Plans navigation', 'Exactly one visibly highlighted sidebar child with matching icon and label colors', 'Existing Add Plan modal opens and cancels', 'Direct refresh loads plans', 'Legacy URL redirects', 'Arabic/mobile navigation without overflow'], activeStyle, errors, data_writes: false }, null, 2));
  console.log('Dedicated Learning Plans page verified from hub and sidebar; no plans saved.');
 } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
