// Local integration verification; only the uniquely named QA profile is deleted.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173', out = 'docs/verification/academy-full-builder';
(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(15000);
  await page.addInitScript(() => { localStorage.setItem('madar.language', 'en'); localStorage.setItem('madar-theme-mode', 'light'); });
  const name = `Local instructor delete QA ${Date.now()}`;
  let fixture;
  async function remove(revision) {
    return page.evaluate(async ({id, revision}) => {
      const { apiFetch, getApiUrl } = await import('/src/utils/apiClient.js');
      const result = await apiFetch(getApiUrl(`/elearning/instructors/${id}`), { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expected_revision: revision, confirmed: true }) });
      return result.status;
    }, { id: fixture.id, revision });
  }
  try {
    await page.goto(origin + '/e-learning/instructors');
    await page.getByRole('button', { name: 'Add Instructor', exact: true }).click();
    await page.getByLabel('Instructor Name', { exact: true }).fill(name);
    const response = page.waitForResponse(r => r.url().endsWith('/api/elearning/instructors') && r.request().method() === 'POST');
    await page.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click();
    const created = await response; expect(created.ok()).toBe(true); fixture = (await created.json()).item;
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await page.reload();
    const row = page.locator('.elearning-directory-row').filter({ hasText: name });
    await expect(row).toBeVisible();
    const action = row.getByRole('button', { name: 'Delete', exact: true });
    await expect(action.locator('.lucide-trash-2')).toBeVisible();
    expect(await action.evaluate(el => getComputedStyle(el).borderTopWidth)).toBe('0px');
    expect(await remove(fixture.revision + 1)).toBe(409);
    await action.click();
    await expect(page.getByRole('dialog')).toContainText('linked user account');
    await page.screenshot({ path: out + '/instructor-delete-confirmation.png', fullPage: true });
    await page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(row).toBeVisible();
    await action.click();
    await page.getByRole('dialog').getByRole('button', { name: 'Delete', exact: true }).click();
    await expect(page.locator('.auth-toast-success')).toContainText('Instructor deleted.');
    await expect(row).toHaveCount(0); fixture = null;
    await page.reload();
    await expect(page.getByRole('button', { name: 'Add Instructor', exact: true })).toBeVisible();
    await expect(row).toHaveCount(0);
    await page.screenshot({ path: out + '/instructor-delete-row.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => localStorage.setItem('madar.language', 'ar'));
    await page.goto(origin + '/e-learning/instructors');
    await expect(page.locator('.elearning-directory-list')).toBeVisible();
    await expect(page.locator('.elearning-directory-row-actions button .lucide-trash-2').first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: out + '/instructor-delete-mobile-rtl.png', fullPage: true });
    fs.writeFileSync(out + '/instructor-delete-results.json', JSON.stringify({ verified_at: new Date().toISOString(), route: '/e-learning/instructors', checks: ['Real temporary profile creation and refresh', 'Borderless Delete icon', 'Stale deletion rejected', 'Confirmation explains retained account and history', 'Cancel preserves record', 'Confirmed deletion and success toast', 'Refresh confirms removal', 'RTL/mobile without horizontal overflow'], temporary_profile_removed: true, existing_profiles_untouched: true }, null, 2));
    console.log('Instructor Delete verified in local browser; QA profile removed.');
  } finally {
    if (fixture && await remove(fixture.revision) !== 200) throw new Error('Temporary instructor cleanup failed');
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
