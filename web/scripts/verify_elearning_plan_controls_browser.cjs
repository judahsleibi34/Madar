// Local, read-only plan dialog verification. No plans are saved.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173', out = 'docs/verification/academy-full-builder';
(async () => {
 const browser = await chromium.launch({ channel: 'chrome', headless: true });
 const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
 const errors = []; page.on('pageerror', error => errors.push(error.message));
 try {
  await page.addInitScript(() => localStorage.setItem('madar.language', 'en'));
  await page.goto(origin + '/e-learning/plans');
  await page.getByRole('button', { name: 'Add Plan', exact: true }).click();
  const dialog = page.getByRole('dialog'), courses = dialog.locator('.elearning-plan-courses');
  await expect(courses).toBeVisible();
  const planStatus = dialog.getByLabel('Plan Status', { exact: true });
  expect(await planStatus.locator('option').evaluateAll(options => options.map(option => option.textContent))).toEqual(['Draft', 'Available to buy', 'Hidden from sale']);
  await planStatus.selectOption('active');
  await expect(dialog.locator('.elearning-plan-status-help')).toHaveText('Learners can see and buy this plan.');
  await planStatus.selectOption('archived');
  await expect(dialog.locator('.elearning-plan-status-help')).toContainText('keep their access');
  await planStatus.selectOption('draft');
  const saveStyle = await dialog.getByRole('button', { name: 'Save', exact: true }).evaluate(node => ({ background: getComputedStyle(node).backgroundColor, color: getComputedStyle(node).color, disabled: node.disabled }));
  expect(saveStyle.background).toBe('rgb(133, 44, 33)'); expect(saveStyle.disabled).toBe(true);
  const desktop = await dialog.evaluate(node => ({ width: node.getBoundingClientRect().width, no_vertical_overflow: node.scrollHeight <= node.clientHeight }));
  expect(desktop.width).toBe(920); expect(desktop.no_vertical_overflow).toBe(true);

  expect(await dialog.getByRole('radio').count()).toBe(0);
  const checks = courses.getByRole('checkbox'); expect(await checks.count()).toBeGreaterThan(1);
  const currency = dialog.locator('select').filter({ has: page.locator('option[value="JOD"]') });
  await expect(currency).toHaveCount(1);
  expect(await currency.locator('option').evaluateAll(options => options.map(option => option.value))).toEqual(['ILS', 'JOD', 'USD', 'EUR']);
  for (const option of await currency.locator('option').all()) expect(await option.textContent()).not.toContain('admin.');
  await currency.selectOption('JOD'); await expect(currency).toHaveValue('JOD');
  await checks.nth(0).check(); await checks.nth(1).check();
  await expect(checks.nth(0)).not.toBeChecked(); await expect(checks.nth(1)).toBeChecked();
  await checks.nth(1).uncheck(); await expect(dialog.getByRole('button', { name: 'Save', exact: true })).toBeDisabled();
  await dialog.getByLabel('Course Access', { exact: true }).selectOption('selected_courses');
  await checks.nth(0).check(); await checks.nth(1).check();
  await expect(checks.nth(0)).toBeChecked(); await expect(checks.nth(1)).toBeChecked();
  const layout = await courses.evaluate(node => {
   const row = node.querySelector('label'), input = row.querySelector('input'), text = row.querySelector('span');
   const a = input.getBoundingClientRect(), b = text.getBoundingClientRect();
   return { border: getComputedStyle(node).borderTopWidth, background: getComputedStyle(node).backgroundColor, row_direction: getComputedStyle(row).flexDirection, aligned: Math.abs((a.top + a.bottom) / 2 - (b.top + b.bottom) / 2) < 2, input_size: a.width };
  });
  expect(layout.border).toBe('0px'); expect(layout.row_direction).toBe('row'); expect(layout.aligned).toBe(true); expect(layout.input_size).toBe(20);
  await dialog.screenshot({ path: out + '/learning-plan-checkbox-currencies.png' });
  await courses.screenshot({ path: out + '/learning-plan-course-checkbox-rows.png' });
  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => localStorage.setItem('madar.language', 'ar'));
  await page.goto(origin + '/e-learning/plans');
  await page.getByRole('button', { name: 'إضافة خطة', exact: true }).click();
  await expect(courses).toBeVisible();
  expect(await dialog.evaluate(node => node.getBoundingClientRect().width <= innerWidth)).toBe(true);
  expect(await dialog.evaluate(node => node.scrollWidth <= node.clientWidth)).toBe(true);
  expect(await courses.locator('label').first().evaluate(node => getComputedStyle(node).flexDirection)).toBe('row');
  await courses.screenshot({ path: out + '/learning-plan-course-checkbox-rtl-mobile.png' });
  await dialog.getByRole('button', { name: 'إلغاء', exact: true }).click();
  expect(errors).toEqual([]);
  fs.writeFileSync(out + '/learning-plan-controls-results.json', JSON.stringify({ verified_at: new Date().toISOString(), route: '/e-learning/plans', checks: ['Checkbox rows without outer border', 'Checkbox and title aligned on one line', 'Single-course scope replaces selection and allows deselection', 'Selected-course scope accepts multiple checks', 'Supported currency dropdown ILS/JOD/USD/EUR with localized labels', 'Friendly Course Access and Plan Status wording', 'Status-specific explanation', 'Red Save button retains disabled behavior', '920px desktop window without vertical scrolling', 'RTL/mobile dialog without horizontal overflow'], layout, desktop, saveStyle, errors, data_writes: false }, null, 2));
  console.log('Course checkbox rows and supported currencies verified; no plans saved.');
 } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
