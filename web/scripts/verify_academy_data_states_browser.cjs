// Local-only editor data-state verification. No saved edits, uploads or fixtures.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173', out = 'docs/verification/academy-full-builder';
(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  await page.addInitScript(() => localStorage.setItem('madar.language', 'en'));
  async function record(id) {
    return page.evaluate(async id => {
      const { apiFetch } = await import('/src/utils/apiClient.js');
      const response = await apiFetch('/api/builder/projects/' + id);
      if (!response.ok) throw Error('Local draft read failed: ' + response.status);
      return (await response.json()).project;
    }, id);
  }
  try {
    await page.goto(origin + '/e-learning/settings/academy');
    await page.getByRole('button', { name: 'Edit Academy', exact: true }).click();
    await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    const id = page.url().match(/projects\/([^/]+)/)[1], before = await record(id);
    await page.getByRole('tab', { name: /^Sections/ }).click();
    for (const name of ['Featured Courses', 'Course Collection', 'Plans / Pricing', 'Instructors', 'Continue Learning']) {
      await page.locator('.section-component-palette').getByRole('button', { name: `${name} Drag into a section`, exact: true }).click();
    }
    await page.locator('.section-component-palette').getByRole('button', { name: 'Instructors Drag into a section', exact: true }).click();
    await expect(page.getByLabel('Heading', { exact: true })).toBeVisible();
    await expect(page.locator('.builder-inspector').getByText(/No eligible items available/)).toBeVisible();
    for (const type of ['academyFeaturedCourses', 'academyCourseCollection', 'academyPlans', 'academyInstructors', 'academyContinueLearning']) {
      const block = page.locator(`[data-academy-component="${type}"]`).first();
      await expect(block).toBeAttached();
      const text = await block.innerText(); expect(text.length).toBeGreaterThan(30);
      expect(text).not.toContain('Loading Academy data');
      expect(text).not.toContain('could not be loaded');
      expect(await block.evaluate(node => node.closest('.direct-element-frame').getBoundingClientRect().height + 1 >= node.getBoundingClientRect().height)).toBe(true);
    }
    await page.locator('.academy-builder-empty[data-academy-component="academyInstructors"]').last().scrollIntoViewIfNeeded();
    await page.screenshot({ path: out + '/academy-data-editor-states.png', fullPage: true });
    // Discard the in-memory Instructor added for inspection, without saving.
    await page.reload(); await expect(page.getByLabel('Page name', { exact: true })).toBeVisible();
    const after = await record(id);
    expect(after.draft_schema).toEqual(before.draft_schema);
    expect(after.draft_revision).toBe(before.draft_revision);
    fs.writeFileSync(out + '/academy-data-state-results.json', JSON.stringify({
      verified_at: new Date().toISOString(), editor: `/page-builder/projects/${id}/pages/sections`,
      checks: ['All five Academy widgets show real eligible data or visible editor setup states', 'Inspector explains empty eligible choices', 'Intrinsic frames fit actual widget content', 'Temporary in-memory component discarded on refresh', 'Saved draft and revision unchanged'],
    }, null, 2));
    console.log('Academy data editor states verified; saved owner draft unchanged.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
