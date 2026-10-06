// Local UI feedback check. Mutation responses are intercepted; no DB writes.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173', out = 'docs/verification/academy-full-builder';
(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.addInitScript(() => { localStorage.setItem('madar.language', 'en'); localStorage.setItem('madar-theme-mode', 'light'); });
  const sample = { id: '00000000-0000-4000-8000-000000000001', name: 'Local toast UI sample', description: 'Unsaved browser-only feedback check', status: 'active', revision: 1 };
  try {
    await page.goto(origin + '/e-learning/groups');
    await page.getByRole('button', { name: 'Create Group', exact: true }).click();
    const dialog = page.getByRole('dialog'), name = page.getByLabel('Group Name', { exact: true });
    await dialog.getByRole('button', { name: 'Save', exact: true }).click();
    const errorToast = dialog.locator('.auth-toast-error');
    await expect(errorToast).toContainText('Enter a Group name.');
    await expect(name).toBeFocused();
    expect(await dialog.locator('form').evaluate(el => el.noValidate)).toBe(true);
    // A native dialog is in the top layer: verify the toast is actually on top.
    await expect.poll(() => errorToast.evaluate(el => {
      const r = el.getBoundingClientRect();
      return el.contains(document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2));
    })).toBe(true);
    await page.screenshot({ path: out + '/directory-validation-toast.png', fullPage: true });
    await name.fill('   '); await dialog.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(errorToast).toContainText('Enter a Group name.');
    await name.fill(sample.name);
    await page.getByLabel('Group Description', { exact: true }).fill(sample.description);
    const endpoint = origin + '/api/elearning/groups';
    await page.route(endpoint, route => route.request().method() === 'POST'
      ? route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Private server diagnostic' }) }) : route.continue());
    await dialog.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(errorToast).toContainText('Could not save this record. Please try again.');
    await expect(name).toHaveValue(sample.name);
    expect(await page.locator('body').innerText()).not.toContain('Private server diagnostic');
    await page.unroute(endpoint);
    await page.route(endpoint, route => route.request().method() === 'POST'
      ? route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify({ item: sample }) }) : route.continue());
    await dialog.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(dialog).toHaveCount(0);
    await expect(page.locator('.auth-toast-success')).toContainText('Group saved.');
    await page.screenshot({ path: out + '/directory-success-toast.png', fullPage: true });
    await page.locator('.auth-toast-success').getByRole('button', { name: 'Dismiss notification' }).click();
    await page.route(endpoint + '/' + sample.id + '/archive', route => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ item: { ...sample, status: 'archived', revision: 2 } }) }));
    const card = page.locator('.elearning-directory-card').filter({ hasText: sample.name });
    await card.getByRole('button', { name: 'Archive', exact: true }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Archive', exact: true }).click();
    await expect(page.locator('.auth-toast-success')).toContainText('Group archived.');
    await page.unrouteAll();
    await page.reload(); await expect(page.getByRole('button', { name: 'Create Group', exact: true })).toBeVisible();
    await expect(page.getByText(sample.name, { exact: true })).toHaveCount(0);
    await page.goto(origin + '/e-learning/instructors');
    await page.getByRole('button', { name: 'Add Instructor', exact: true }).click();
    await page.getByLabel('Instructor Name', { exact: true }).fill('Local validation sample');
    await page.getByLabel('Email (optional)', { exact: true }).fill('bad-email');
    await page.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click();
    await expect(page.getByRole('dialog').locator('.auth-toast-error')).toContainText('Enter a valid email address.');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => localStorage.setItem('madar.language', 'ar'));
    await page.goto(origin + '/e-learning/groups');
    await page.locator('.elearning-course-toolbar button').click();
    await page.getByRole('dialog').locator('button[type="submit"]').click();
    await expect(page.getByRole('dialog').locator('.auth-toast')).toHaveAttribute('dir', 'rtl');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    fs.writeFileSync(out + '/directory-toast-results.json', JSON.stringify({ verified_at: new Date().toISOString(), routes: ['/e-learning/groups', '/e-learning/instructors'], checks: ['Required and whitespace-only name toast replaces browser validation bubble', 'Invalid instructor email toast', 'Toast visible above native modal', 'Simulated failed save keeps values and hides raw diagnostics', 'Simulated save and archive show global success toast after modal closes', 'Refresh removes browser-only sample', 'RTL/mobile toast without overflow'], database_writes: false, mutation_responses: 'intercepted local UI fixtures' }, null, 2));
    console.log('Directory validation, failure, success and RTL/mobile toasts verified; no DB writes.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
