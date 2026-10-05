// Local navigation/layout verification; never saves or publishes the owner draft.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173', out = 'docs/verification/academy-full-builder';
(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  await page.addInitScript(() => {
    localStorage.setItem('madar.language', 'en');
    localStorage.setItem('madar-theme-mode', 'dark');
  });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  async function record(id) {
    return page.evaluate(async id => {
      const { apiFetch } = await import('/src/utils/apiClient.js');
      const response = await apiFetch('/api/builder/projects/' + id);
      if (!response.ok) throw Error('Owner draft lookup failed: ' + response.status);
      return (await response.json()).project;
    }, id);
  }
  try {
    await page.goto(origin + '/e-learning/landing-page');
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    const editor = new URL(page.url()).pathname;
    expect(editor).toMatch(/^\/e-learning\/landing-page\/projects\/[^/]+\/pages$/);
    const id = editor.match(/projects\/([^/]+)/)[1], before = await record(id);
    const base = `/e-learning/landing-page/projects/${id}`;
    await page.getByRole('link', { name: 'Header & Footer', exact: true }).click();
    await expect(page).toHaveURL(origin + base + '/header-footer');
    await page.getByRole('link', { name: 'Publish', exact: true }).click();
    await expect(page).toHaveURL(origin + base + '/publish');
    await expect(page.getByRole('heading', { name: 'Public site link', exact: true })).toBeVisible();
    await expect(page.getByRole('toolbar', { name: 'Artboard zoom' })).toHaveCount(0);
    const workspace = await page.locator('.publish-workspace').boundingBox();
    expect(workspace.width).toBeLessThanOrEqual(1200);
    const share = await page.locator('.publish-link-actions a').boundingBox();
    const preview = await page.getByRole('button', { name: 'Preview site', exact: true }).boundingBox();
    expect(share.width).toBeLessThan(300); expect(preview.width).toBeLessThan(220);
    await page.screenshot({ path: out + '/academy-publish-compact-dark.png', fullPage: true });
    await page.reload();
    await expect(page.getByRole('heading', { name: 'Public site link', exact: true })).toBeVisible();
    await expect(page).toHaveURL(origin + base + '/publish');
    await page.getByRole('link', { name: 'Pages', exact: true }).click();
    await page.getByRole('tab', { name: /^Sections/ }).click();
    await expect(page).toHaveURL(origin + base + '/pages/sections');
    await page.getByRole('tab', { name: /^Themes/ }).click();
    await expect(page).toHaveURL(origin + base + '/pages/themes');
    await page.screenshot({ path: out + '/academy-dedicated-editor.png', fullPage: true });
    await page.goto(origin + `/page-builder/projects/${id}/pages`);
    await expect(page).toHaveURL(origin + editor);
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    await page.goto(origin + base + '/preview');
    await expect(page.locator('.tenant-runtime-page')).toBeVisible();
    await expect(page).toHaveURL(origin + base + '/preview');
    await page.goto(origin + '/e-learning/landing-page/projects/00000000-0000-0000-0000-000000000000/pages');
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page.locator('.page-builder')).toHaveCount(0);
    await page.goto(origin + '/e-learning/landing-page');
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    const after = await record(id);
    expect(after.draft_schema).toEqual(before.draft_schema);
    expect(after.draft_revision).toBe(before.draft_revision);
    expect(errors).toEqual([]);
    fs.writeFileSync(out + '/academy-namespace-results.json', JSON.stringify({
      verified_at: new Date().toISOString(), editor, publish: base + '/publish', preview: base + '/preview',
      checks: ['Separate E-Learning entry and editor routes', 'Header/Footer, Publish, Sections and Themes stay in E-Learning', 'Refresh stays in E-Learning Publish', 'Old Academy Builder bookmark redirects into dedicated editor', 'Dedicated draft-preview route renders', 'Guessed unrelated project does not mount editor', 'Publish content capped at 1200px with compact action buttons', 'Owner draft/revision unchanged', 'Plan assignments intentionally deferred; existing permissions remain'], errors,
    }, null, 2));
    console.log('Dedicated Academy editor routes and compact Publish UI verified.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
