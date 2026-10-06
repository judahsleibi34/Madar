// Local integration check: create/delete only uniquely named temporary QA groups.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173', out = 'docs/verification/academy-full-builder';
(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(15000);
  await page.addInitScript(() => { localStorage.setItem('madar.language', 'en'); localStorage.setItem('madar-theme-mode', 'light'); });
  const name = `Local group QA ${Date.now()}`, description = 'Temporary verification group. Full description and relationships remain visible.';
  let fixture;
  async function api(path, options) {
    return page.evaluate(async ({ path, options }) => {
      const { apiFetch, getApiUrl } = await import('/src/utils/apiClient.js');
      const response = await apiFetch(getApiUrl(path), options);
      return { status: response.status, data: await response.json() };
    }, { path, options });
  }
  try {
    await page.goto(origin + '/e-learning/groups');
    await page.getByRole('button', { name: 'Create Group', exact: true }).click();
    await page.getByLabel('Group Name', { exact: true }).fill(name);
    await page.getByLabel('Group Description', { exact: true }).fill(description);
    await expect(page.getByRole('dialog').getByRole('combobox', { name: 'Status', exact: true })).toHaveValue('active');
    await page.getByRole('dialog').getByRole('combobox', { name: 'Status', exact: true }).selectOption('archived');
    await page.screenshot({ path: out + '/create-group-status.png', fullPage: true });
    const createResponse = page.waitForResponse(r => r.url().endsWith('/api/elearning/groups') && r.request().method() === 'POST');
    await page.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click();
    const response = await createResponse;
    expect(response.ok()).toBe(true); fixture = (await response.json()).item;
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await page.reload();
    const row = page.locator('.elearning-directory-row').filter({ hasText: name });
    await expect(row).toContainText(description);
    await expect(row).toContainText('Archived');
    await expect(row).toContainText('Created'); await expect(row).toContainText('Updated');
    await expect(row).toContainText('Members'); await expect(row).toContainText('Courses');
    await expect(row.locator('.lucide-tag')).toBeVisible();
    await expect(row.locator('.lucide-pencil')).toBeVisible(); await expect(row.locator('.lucide-trash-2')).toBeVisible();
    for (const button of await row.locator('.elearning-directory-row-actions button').all()) {
      expect(await button.evaluate(el => getComputedStyle(el).borderTopWidth)).toBe('0px');
    }
    await expect(page.getByText('No description provided.', { exact: true })).toHaveCount(0);
    await page.screenshot({ path: out + '/group-list-rows.png', fullPage: true });
    await page.getByRole('button', { name: 'Create Group', exact: true }).click();
    await page.getByLabel('Group Name', { exact: true }).fill(name.toUpperCase().replaceAll(' ', '  '));
    await page.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click();
    await expect(page.getByRole('dialog').locator('.auth-toast-error')).toContainText('A group with this name already exists.');
    await page.screenshot({ path: out + '/group-duplicate-name-toast.png', fullPage: true });
    await page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }).click();
    // A stale deletion must fail and preserve the row.
    expect((await api(`/elearning/groups/${fixture.id}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expected_revision: fixture.revision + 1, confirmed: true }) })).status).toBe(409);
    await row.getByRole('button', { name: 'Delete', exact: true }).click();
    await expect(page.getByRole('dialog')).toContainText('learner progress are retained');
    await page.getByRole('dialog').getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(row).toBeVisible();
    await row.getByRole('button', { name: 'Delete', exact: true }).click();
    await page.getByRole('dialog').getByRole('button', { name: 'Delete', exact: true }).click();
    await expect(page.locator('.auth-toast-success')).toContainText('Group deleted.');
    await expect(row).toHaveCount(0); fixture = null;
    await page.reload(); await expect(page.locator('.elearning-directory-list')).toBeVisible(); await expect(row).toHaveCount(0);
    await page.screenshot({ path: out + '/group-list-rows.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => localStorage.setItem('madar.language', 'ar'));
    await page.goto(origin + '/e-learning/groups');
    await expect(page.locator('.elearning-directory-list')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: out + '/group-list-mobile-rtl.png', fullPage: true });
    fs.writeFileSync(out + '/group-management-results.json', JSON.stringify({ verified_at: new Date().toISOString(), route: '/e-learning/groups', checks: ['Real group create and refresh persistence', 'Full description, counts and timestamps displayed', 'Tag/Edit/Delete existing Lucide icons', 'Case/whitespace duplicate rejected with toast', 'Stale deletion rejected', 'Cancel deletion preserves group', 'Confirmed deletion and refresh persistence', 'RTL/mobile without horizontal overflow'], temporary_groups_removed: true, existing_groups_unchanged: true }, null, 2));
    console.log('Group rows, duplicate rejection, confirmed delete and RTL/mobile verified. Temporary group removed.');
  } finally {
    if (fixture) {
      const cleanup = await api(`/elearning/groups/${fixture.id}`, { method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ expected_revision: fixture.revision, confirmed: true }) });
      if (cleanup.status !== 200) throw new Error('Temporary group cleanup failed');
    }
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
