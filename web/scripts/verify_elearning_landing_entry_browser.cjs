// Local-only navigation verification; does not save, publish or seed content.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173', out = 'docs/verification/academy-full-builder';
(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => localStorage.setItem('madar.language', 'en'));
  async function record(id) {
    return page.evaluate(async id => {
      const { apiFetch } = await import('/src/utils/apiClient.js');
      const response = await apiFetch('/api/builder/projects/' + id);
      if (!response.ok) throw Error('Project read failed: ' + response.status);
      return (await response.json()).project;
    }, id);
  }
  async function checkSubmenu() {
    const expand = page.getByRole('button', { name: 'Expand sidebar', exact: true });
    if (await expand.isVisible()) await expand.click();
    const parent = page.getByRole('button', { name: 'E-Learning', exact: true });
    if (await parent.getAttribute('aria-expanded') !== 'true') await parent.click();
    const group = page.locator('#dashboard-sidebar-elearning');
    for (const name of ['Courses', 'Groups', 'Instructors', 'Learning Plans', 'Landing Page', 'Academy & Access', 'Settings']) {
      const link = group.getByRole('link', { name, exact: true });
      await expect(link).toBeVisible();
      await expect(link.locator('span')).toBeVisible();
      expect(await link.locator('svg').count()).toBe(1);
      expect(await link.evaluate(node => getComputedStyle(node).justifyContent)).toBe('flex-start');
    }
    return group;
  }
  try {
    await page.goto(origin + '/e-learning/courses');
    let group = await checkSubmenu();
    await page.screenshot({ path: out + '/elearning-landing-menu.png', fullPage: true });
    await group.getByRole('link', { name: 'Landing Page', exact: true }).click();
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    const editor = new URL(page.url()).pathname, id = editor.match(/projects\/([^/]+)/)[1];
    expect(editor).toBe(`/e-learning/landing-page/projects/${id}/pages`);
    const before = await record(id); expect(before.usage_profile).toBe('academy');
    const expand = page.getByRole('button', { name: 'Expand sidebar', exact: true });
    if (await expand.isVisible()) await expand.click();
    group = await checkSubmenu();
    await page.screenshot({ path: out + '/elearning-landing-builder-sidebar.png', fullPage: true });
    await group.getByRole('link', { name: 'Landing Page', exact: true }).click();
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    await expect(page).toHaveURL(origin + editor);
    await page.getByRole('button', { name: 'Preview site', exact: true }).click();
    // Native landing header destinations enter the existing fixed platform.
    await page.getByRole('button', { name: 'Courses', exact: true }).click();
    await expect(page).toHaveURL(origin + '/academy/testing/courses');
    await expect(page.locator('.academy-grid')).toBeVisible();
    await page.screenshot({ path: out + '/landing-existing-course-platform.png', fullPage: true });
    await page.getByRole('link', { name: 'My Learning', exact: true }).first().click();
    await expect(page).toHaveURL(origin + '/my-learning');
    await page.screenshot({ path: out + '/landing-existing-student-platform.png', fullPage: true });
    await page.goto(origin + '/e-learning/landing-page');
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    const after = await record(id);
    expect(after.draft_schema).toEqual(before.draft_schema);
    expect(after.draft_revision).toBe(before.draft_revision);
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => localStorage.setItem('madar.language', 'ar'));
    await page.goto(origin + '/e-learning/courses');
    await page.locator('.dashboard-mobile-menu-button').click();
    const parent = page.locator('[aria-controls="dashboard-sidebar-elearning"]');
    if (await parent.getAttribute('aria-expanded') !== 'true') await parent.click();
    const mobileGroup = page.locator('#dashboard-sidebar-elearning');
    await expect(mobileGroup).toBeVisible();
    expect(await page.locator('#dashboard-sidebar').getAttribute('dir')).toBe('rtl');
    for (const label of await mobileGroup.locator('a > span').all()) await expect(label).toBeVisible();
    expect(await mobileGroup.locator('a > span').count()).toBe(7);
    await page.screenshot({ path: out + '/elearning-sidebar-rtl-mobile.png', fullPage: true });
    await page.goto(origin + '/e-learning/landing-page');
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await page.screenshot({ path: out + '/landing-entry-rtl-mobile.png', fullPage: true });
    expect(errors).toEqual([]);
    fs.writeFileSync(out + '/landing-entry-results.json', JSON.stringify({
      verified_at: new Date().toISOString(), entry: '/e-learning/landing-page', editor,
      catalog: '/academy/testing/courses', student: '/my-learning', errors,
      checks: ['Visible labels and icons on expanded main and Builder sidebar', 'Normal Landing Page menu opens saved owner Academy', 'Repeated entry reuses same project', 'Native landing preview Courses action opens fixed catalog', 'Catalog My Learning opens fixed learner platform', 'Owner draft and revision unchanged', 'Arabic RTL mobile drawer shows all seven submenu labels', 'Mobile entry opens same Builder without overflow'],
    }, null, 2));
    console.log('E-Learning Landing Page entry and existing course platform verified:', editor);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
