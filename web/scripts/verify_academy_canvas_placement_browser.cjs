// Local-only canvas verification. Restores the owner's original draft with a
// revision guard; never publishes and never deletes/rebinds an owner project.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173', out = 'docs/verification/academy-full-builder';
(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.addInitScript(() => localStorage.setItem('madar.language', 'en'));
  let original, changed = false, lastVerified;
  page.on('response', async response => {
    if (original && response.url().endsWith('/builder/projects/' + original.id) && response.request().method() === 'PUT' && response.ok()) {
      lastVerified = (await response.json()).project;
    }
  });
  async function api(path, method = 'GET', data) {
    return page.evaluate(async ({ path, method, data }) => {
      const { apiFetch } = await import('/src/utils/apiClient.js');
      const response = await apiFetch('/api' + path, { method,
        headers: { 'Content-Type': 'application/json', 'X-Madar-Builder-Contract': 'cloud-draft-v1' },
        ...(data ? { body: JSON.stringify(data) } : {}),
      });
      if (!response.ok) throw Error(path + ' status ' + response.status);
      return response.json();
    }, { path, method, data });
  }
  async function save() {
    const response = page.waitForResponse(r => r.url().endsWith('/builder/projects/' + original.id) && r.request().method() === 'PUT');
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    const result = await response;
    if (!result.ok()) console.error('Save rejected:', result.status(), await result.json());
    expect(result.ok()).toBe(true);
    lastVerified = (await api('/builder/projects/' + original.id)).project;
  }
  try {
    await page.goto(origin + '/e-learning/settings/academy');
    await page.getByRole('button', { name: 'Edit Academy', exact: true }).click();
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    const id = page.url().match(/projects\/([^/]+)/)[1];
    original = (await api('/builder/projects/' + id)).project;
    expect(original.usage_profile).toBe('academy');
    fs.writeFileSync('/tmp/madar-academy-placement-original.json', JSON.stringify(original));
    await page.getByRole('tab', { name: /^Sections/ }).click();
    await expect(page.locator('.builder-section-composition')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Add section', exact: true })).toHaveCount(0);
    const frame = page.locator('.direct-layout-frame');
    await expect(frame).toHaveCount(1);
    const before = await frame.locator('.direct-element-frame').count();
    const text = page.locator('.section-component-palette button').filter({ has: page.getByText('Text', { exact: true }) });
    await text.dragTo(frame, { targetPosition: { x: 260, y: 300 } });
    await expect(frame.locator('.direct-element-frame')).toHaveCount(before + 1);
    changed = true;
    await expect(frame.locator('.direct-element-frame.is-selected')).toHaveCount(1);
    const selected = frame.locator('.direct-element-frame.is-selected');
    const initialX = await selected.getAttribute('data-logical-x');
    const handle = await page.getByRole('button', { name: 'Move Text', exact: true }).boundingBox();
    await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
    await page.mouse.down();
    await page.mouse.move(handle.x + handle.width / 2 + 70, handle.y + handle.height / 2 + 40, { steps: 10 });
    await page.mouse.up();
    await expect.poll(() => selected.getAttribute('data-logical-x')).not.toBe(initialX);
    await page.screenshot({ path: out + '/native-canvas-placement.png', fullPage: true });
    await save();
    const persisted = lastVerified.draft_schema;
    expect(persisted.pages[0].sections).toHaveLength(1);
    expect(persisted.pages[0].sections[0].isPageCanvas).toBe(true);
    await page.reload(); await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    await expect(page.locator('.direct-element-frame')).toHaveCount(before + 1);
    expect((await api('/builder/projects/' + id)).project.draft_schema).toEqual(persisted);
    await page.getByRole('tab', { name: /^Sections/ }).click();
    const afterReload = await page.locator('.direct-element-frame').count();
    await page.locator('.section-component-palette button').filter({ has: page.getByText('Heading', { exact: true }) }).click();
    await expect(page.locator('.direct-element-frame')).toHaveCount(afterReload + 1);
    await save();
    fs.writeFileSync(out + '/canvas-placement-results.json', JSON.stringify({
      verified_at: new Date().toISOString(), route: `/page-builder/projects/${id}/pages/sections`,
      checks: ['No extra Sections list', 'One native continuous canvas', 'Real palette drag-and-drop adds and selects Text', 'Move handle changes placed component coordinates', 'Save and refresh preserve placement', 'Palette click adds Heading'],
      published_unchanged: lastVerified.published_schema === null && original.published_schema === null,
    }, null, 2));
    console.log('Native Academy canvas placement verified.');
  } catch (error) {
    console.error('Browser verification failed:', error);
    await page.screenshot({ path: out + '/canvas-placement-failure.png', fullPage: true });
    throw error;
  } finally {
    try {
      if (original && changed) {
        const current = (await api('/builder/projects/' + original.id)).project;
        if (lastVerified || current.draft_revision !== original.draft_revision) {
          if (!lastVerified || current.draft_revision !== lastVerified.draft_revision) throw Error('Draft changed outside verification; original snapshot retained in /tmp, restoration refused');
          await api('/builder/projects/' + original.id, 'PUT', {
            name: original.name, slug: original.slug, draft_schema: original.draft_schema, expected_revision: current.draft_revision,
          });
          console.log('Original owner draft restored through authorized revision-guarded API.');
        }
      }
    } finally { await browser.close(); }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
