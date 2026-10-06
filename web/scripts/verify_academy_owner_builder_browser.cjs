// Local owner UI parity check. Creates one unpublished website fixture, then archives it.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173';
const out = 'docs/verification/academy-full-builder';

(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.addInitScript(() => localStorage.setItem('madar.language', 'en'));
  let fixture;
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  async function api(path, method = 'GET', data) {
    return page.evaluate(async ({ path, method, data }) => {
      const { apiFetch } = await import('/src/utils/apiClient.js');
      const response = await apiFetch('/api' + path, {
        method, headers: { 'Content-Type': 'application/json', 'X-Madar-Builder-Contract': 'cloud-draft-v1' },
        ...(data ? { body: JSON.stringify(data) } : {}),
      });
      if (!response.ok) throw Error(path + ' status ' + response.status);
      return response.json();
    }, { path, method, data });
  }
  async function inspectEditor() {
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    await page.getByRole('tab', { name: /^Sections/ }).click();
    await expect(page.getByRole('heading', { name: 'Components', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Add section', exact: true })).toHaveCount(0);
    const shared = await page.evaluate(() => ({
      sidebar: document.querySelectorAll('.builder-sidebar').length,
      canvas: document.querySelectorAll('.builder-canvas-shell').length,
      inspector: document.querySelectorAll('.builder-inspector').length,
      subbar: document.querySelectorAll('.builder-subbar').length,
      composition: document.querySelectorAll('.builder-section-composition').length,
      tools: [...document.querySelectorAll('[role="tablist"][aria-label="Editing tools"] [role="tab"] strong')].map(node => node.textContent),
    }));
    await page.getByRole('tab', { name: /^Themes/ }).click();
    await expect(page.locator('.builder-themes-panel')).toBeVisible();
    await page.getByRole('tab', { name: /^Sections/ }).click();
    return shared;
  }
  try {
    await page.goto(origin + '/e-learning/settings/academy');
    await page.getByRole('button', { name: 'Edit Academy', exact: true }).click();
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    const academyId = page.url().match(/projects\/([^/]+)/)[1];
    const academy = (await api('/builder/projects/' + academyId)).project;
    expect(academy.usage_profile).toBe('academy');
    const expectedDraft = await page.evaluate(async record => {
      const { getDraftProjectFromRecordWithRepairs } = await import('/src/components/PageBuilder/core/PageBuilder.project.js');
      const { serializePersistableProject } = await import('/src/components/PageBuilder/core/PageBuilder.editorState.js');
      return serializePersistableProject(getDraftProjectFromRecordWithRepairs(record).project);
    }, academy);
    const academyUI = await inspectEditor();
    await page.screenshot({ path: out + '/shared-academy-builder.png', fullPage: true });
    const draft = await page.evaluate(async () => {
      const { createBlankWorkspaceProject } = await import('/src/components/PageBuilder/core/PageBuilder.starters.js');
      const { cleanBuilderProject } = await import('/src/components/PageBuilder/core/PageBuilder.project.js');
      return cleanBuilderProject(createBlankWorkspaceProject());
    });
    fixture = (await api('/builder/projects', 'POST', {
      name: 'Local Builder parity verification', slug: 'builder-parity-' + Date.now(), draft_schema: draft,
    })).project;
    expect(fixture.usage_profile).toBe('website');
    expect(fixture.id).not.toBe(academyId);
    // Save the unchanged Academy through the real UI so it is the most recent
    // project. Regular Builder must still select only a website.
    await page.goto(origin + '/e-learning/settings/academy');
    await page.getByRole('button', { name: 'Edit Academy', exact: true }).click();
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    const saved = page.waitForResponse(response => response.url().endsWith('/builder/projects/' + academyId) && response.request().method() === 'PUT');
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    expect((await saved).ok()).toBe(true);
    await page.goto(origin + '/page-builder');
    await expect(page).toHaveURL(origin + `/page-builder/projects/${fixture.id}/pages`);
    const websiteUI = await inspectEditor();
    expect(websiteUI).toEqual(academyUI);
    await page.screenshot({ path: out + '/shared-website-builder.png', fullPage: true });
    const websiteIds = (await api('/builder/projects?usage_profile=website')).projects.map(project => project.id);
    const academyIds = (await api('/builder/projects?usage_profile=academy')).projects.map(project => project.id);
    expect(websiteIds).toContain(fixture.id); expect(websiteIds).not.toContain(academyId);
    expect(academyIds).toContain(academyId); expect(academyIds).not.toContain(fixture.id);
    await page.goto(origin + '/e-learning/settings/academy');
    await page.getByRole('button', { name: 'Edit Academy', exact: true }).click();
    await expect(page).toHaveURL(origin + `/page-builder/projects/${academyId}/pages`);
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    await page.reload(); await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    const reopened = (await api('/builder/projects/' + academyId)).project;
    // Explicit Save can persist normal Builder compatibility defaults. Compare
    // canonical content, not the pre-normalization seed's omitted fields.
    const reopenedDraft = await page.evaluate(async record => {
      const { getDraftProjectFromRecordWithRepairs } = await import('/src/components/PageBuilder/core/PageBuilder.project.js');
      const { serializePersistableProject } = await import('/src/components/PageBuilder/core/PageBuilder.editorState.js');
      return serializePersistableProject(getDraftProjectFromRecordWithRepairs(record).project);
    }, reopened);
    expect(reopenedDraft).toBe(expectedDraft);
    expect(reopened.published_schema).toEqual(academy.published_schema);
    expect(errors).toEqual([]);
    fs.writeFileSync(out + '/owner-builder-results.json', JSON.stringify({
      verified_at: new Date().toISOString(), academy_project: academyId,
      editor: `/page-builder/projects/${academyId}/pages`, sharedUI: academyUI,
      checks: ['Shared website/Academy editor shell and tools', 'Theme access through same sidebar', 'Separate website/Academy saved projects', 'Server-side profile filtering', 'Normal Builder entry opens website project', 'E-Learning Edit reopens same unchanged Academy draft', 'Refresh persistence'],
      website_fixture: fixture.id, errors,
    }, null, 2));
    console.log('Owner project isolation and native Builder UI parity verified.');
  } finally {
    if (fixture?.id) {
      const current = (await api('/builder/projects/' + fixture.id)).project;
      expect(current.usage_profile).toBe('website'); expect(current.published_schema).toBeFalsy();
      await api('/builder/projects/' + fixture.id, 'DELETE');
      const resultPath = out + '/owner-builder-results.json';
      if (fs.existsSync(resultPath)) {
        const result = JSON.parse(fs.readFileSync(resultPath));
        if (result.website_fixture === fixture.id) {
          result.website_fixture_cleanup = 'Archived through normal authorized Builder API; unpublished and unbound';
          fs.writeFileSync(resultPath, JSON.stringify(result, null, 2));
        }
      }
      console.log('Unpublished website verification fixture archived:', fixture.id);
    }
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
