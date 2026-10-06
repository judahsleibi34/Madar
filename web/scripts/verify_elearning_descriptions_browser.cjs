// Read-only local UI check: edits are cancelled; no content is saved.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173', out = 'docs/verification/academy-full-builder';
(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, permissions: ['clipboard-read', 'clipboard-write'] });
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  await page.addInitScript(() => { localStorage.setItem('madar.language', 'en'); localStorage.setItem('madar-theme-mode', 'light'); });
  const checks = [];
  const sample = 'A long description should remain readable, wrap within the field, and keep the other labels available. '.repeat(18) + '\n'.repeat(20);
  async function pasteAndCheck(label, file) {
    const dialog = page.getByRole('dialog'), field = dialog.locator('textarea.elearning-description-textarea');
    await field.focus();
    await page.evaluate(text => navigator.clipboard.writeText(text), sample);
    await field.press('Control+V');
    await expect(field).toHaveValue(sample);
    await expect(dialog.locator('.elearning-description-count')).toHaveCount(0);
    await expect(field).toHaveAttribute('maxlength', '4000');
    await expect.poll(() => field.evaluate(el => el.scrollTop)).toBe(0);
    const metrics = await field.evaluate(el => ({ height: el.clientHeight, wrapped: getComputedStyle(el).overflowWrap, fit: el.scrollWidth <= el.clientWidth }));
    expect(metrics.height).toBeGreaterThan(140); expect(metrics.height).toBeLessThanOrEqual(320); expect(metrics.fit).toBe(true);
    await expect(dialog.getByRole('button', { name: 'Cancel', exact: true })).toBeVisible();
    if (file) await page.screenshot({ path: `${out}/${file}`, fullPage: true });
    checks.push({ field: label, ...metrics, exact_clipboard_value: true, top_visible_after_paste: true });
    await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
  }
  try {
    for (const [route, button, label, file] of [
      ['/e-learning/groups', 'Create Group', 'Group Description', 'groups-long-description.png'],
      ['/e-learning/instructors', 'Add Instructor', 'Instructor Biography', 'instructors-long-description.png'],
      ['/e-learning/plans', 'Add Plan', 'Plan Description', 'plans-long-description.png'],
      ['/e-learning/courses', 'Create Course', 'Course Description', null],
    ]) {
      await page.goto(origin + route); await page.getByRole('button', { name: button, exact: true }).click();
      await pasteAndCheck(label, file);
      console.log(`Verified ${label}`);
    }
    // Open existing Structure via its normal course management link.
    await page.getByRole('link', { name: 'Manage', exact: true }).first().click();
    await page.getByRole('link', { name: 'Structure', exact: true }).click();
    await page.getByRole('button', { name: 'Add Section', exact: true }).first().click();
    await pasteAndCheck('Section Description');
    await page.getByRole('button', { name: 'Add Lesson', exact: true }).first().click();
    await pasteAndCheck('Lesson Description');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => localStorage.setItem('madar.language', 'ar'));
    await page.goto(origin + '/e-learning/plans');
    await page.locator('.ecommerce-page-header button').click();
    const field = page.getByRole('dialog').locator('textarea.elearning-description-textarea');
    await field.fill('وصف طويل يجب أن يبقى واضحاً وتظهر بقية الحقول. '.repeat(45));
    expect(await field.evaluate(el => getComputedStyle(el).direction)).toBe('rtl');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    expect(await field.evaluate(el => el.scrollWidth <= el.clientWidth)).toBe(true);
    await page.screenshot({ path: out + '/plans-long-description-mobile-rtl.png', fullPage: true });
    checks.push({ field: 'Plan Description', rtl_mobile: true, horizontal_overflow: false });
    fs.writeFileSync(out + '/description-fields-results.json', JSON.stringify({ verified_at: new Date().toISOString(), checks, database_writes: false }, null, 2));
    console.log('Descriptions verified with real clipboard paste and RTL/mobile; no saves.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
