// Loopback-only QA: temporarily changes registration policy, restores it in finally.
// Does not create users, send email, publish content or modify an Academy draft.
const { chromium, expect } = require('../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const origin = 'http://localhost:5173', out = 'docs/verification/academy-full-builder';
(async () => {
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  let original, changed = false;
  async function settings(values) {
    return page.evaluate(async values => {
      const { fetchELearningSettings, saveELearningSettings } = await import('/src/services/elearningSettings.js');
      return values ? saveELearningSettings(values) : fetchELearningSettings();
    }, values);
  }
  try {
    await page.addInitScript(() => localStorage.setItem('madar.language', 'en'));
    await page.goto(origin + '/e-learning/academy-access');
    await expect(page.getByRole('combobox')).toBeVisible();
    original = (await settings()).settings;
    expect(original.academy_enabled).toBe(true);
    await page.getByRole('combobox').selectOption('email_domain');
    await page.getByLabel('Allowed email domains').fill('jack@University.edu, university.edu, college.edu');
    changed = true;
    await page.getByRole('button', { name: 'Save Changes' }).click();
    await expect(page.getByRole('status')).toBeVisible();
    await page.reload();
    await expect(page.getByRole('combobox')).toHaveValue('email_domain');
    await expect(page.getByLabel('Allowed email domains')).toHaveValue('university.edu, college.edu');
    expect((await settings()).settings.academy_email_domains).toEqual(['university.edu', 'college.edu']);
    await page.locator('.academy-management-access').screenshot({ path: out + '/academy-email-domain-access.png' });
    const denied = await page.evaluate(async () => {
      const { registerAcademy } = await import('/src/services/elearningAcademy.js');
      const results = [];
      for (const email of ['jack@gmail.com', 'jack@university.edu.attacker.com', 'jack@student.university.edu']) {
        try { await registerAcademy('testing', { full_name: 'Domain QA', email, password: 'Safe-password-123' }); throw Error('Unexpected signup success'); }
        catch (error) { results.push({ status: error.status, code: error.code }); }
      }
      return results;
    });
    denied.forEach(result => { expect(result.status).toBe(403); expect(result.code).toBe('academy_email_domain_not_allowed'); });
    await page.goto(origin + '/academy/testing/login?register=1');
    await expect(page.getByRole('heading', { name: 'Create Account' })).toBeVisible();
    await page.getByLabel('Full name').fill('Jack');
    await page.getByLabel('Email', { exact: true }).fill('jack@gmail.com');
    await page.getByLabel('Password', { exact: true }).fill('Safe-password-123');
    await page.getByRole('button', { name: 'Create Account', exact: true }).click();
    await expect(page.getByRole('alert')).toHaveText('Use an email address from a domain allowed by this Academy.');
    await page.screenshot({ path: out + '/academy-email-domain-signup.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(() => localStorage.setItem('madar.language', 'ar'));
    await page.goto(origin + '/e-learning/academy-access');
    await expect(page.getByRole('combobox')).toHaveValue('email_domain');
    expect(await page.locator('.academy-management-hub').getAttribute('dir')).toBe('rtl');
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.getByLabel('نطاقات البريد المسموح بها')).toBeVisible();
    await page.locator('.academy-management-access').screenshot({ path: out + '/academy-email-domain-rtl-mobile.png' });
    expect(errors).toEqual([]);
    fs.writeFileSync(out + '/academy-email-domain-results.json', JSON.stringify({ verified_at: new Date().toISOString(), owner_route: '/e-learning/academy-access', signup_route: '/academy/testing/login?register=1', checks: ['Third Email domain option', 'Real local API save and refresh persistence', 'Example email domain extraction, case normalization and deduplication; only domains saved', 'Direct signup form without invitation', 'Server rejects unlisted domains and suffix/subdomain spoofing before account creation', 'Authored browser signup error', 'Arabic RTL mobile without overflow'], denied, errors, no_users_created: true, no_email_sent: true }, null, 2));
    console.log('Email domain registration verified with real local API and RTL/mobile.');
  } finally {
    if (changed && original) {
      await page.goto(origin + '/e-learning/academy-access');
      await expect(page.getByRole('combobox')).toBeVisible();
      const current = (await settings()).settings;
      await settings({ ...current, academy_registration: original.academy_registration, academy_email_domains: original.academy_email_domains || [] });
      const restored = (await settings()).settings;
      expect(restored.academy_registration).toBe(original.academy_registration);
      expect(restored.academy_email_domains).toEqual(original.academy_email_domains || []);
      console.log('Original registration policy restored.');
    }
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
