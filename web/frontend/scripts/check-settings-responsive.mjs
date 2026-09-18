import assert from "node:assert/strict";
import { chromium, expect } from "@playwright/test";

const origin = new URL(process.argv[2] || "http://127.0.0.1:5189");
assert(["127.0.0.1", "localhost", "[::1]"].includes(origin.hostname), "Settings checks require a loopback frontend");
const browser = await chromium.launch({ headless: true });
const user = { id: 24, tenant_id: 7, first_name: "Madar", last_name: "Owner", email: "owner@example.com", user_type: "user", subscription_type: "full_platform", plan: "business" };
const website = { brand: "Form & Flow", footer_store_name: "Madar Store", description: "A store description that wraps on smaller screens.", contact_email: "shop@example.com", phone: "+15550102026", standard_path_slug: "madar-demo", ecommerce_theme: {} };
let passed = 0;
try {
  for (const width of [320, 390, 768, 1024, 1440]) {
    for (const locale of ["en", "ar"]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      await page.addInitScript(locale => localStorage.setItem("madar.language", locale), locale);
      await page.route("**/*", route => {
        const url = new URL(route.request().url());
        const path = url.pathname;
        const json = data => route.fulfill({ contentType: "application/json", body: JSON.stringify(data) });
        if (path.endsWith("/auth/user_status")) return json({ logged_in: true, user, csrf_token: "test-csrf-token" });
        if (path.endsWith("/auth/mfa/enroll")) return json({ factor: { id: "new-factor" }, totp: { qr_code: "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"100\" height=\"100\"><rect width=\"100\" height=\"100\" /></svg>", uri: "otpauth://totp/Madar:owner@example.com?secret=TESTONLY&issuer=Madar" } });
        if (path.endsWith("/auth/mfa/status")) return json({ factors: [{ id: "factor-1", friendly_name: "Authenticator", status: "verified", factor_type: "totp" }], current_level: "aal1", next_level: "aal2" });
        if (path.endsWith("/website/settings")) return json({ website });
        if (path.endsWith("/ecommerce/settings")) return json({ currency: "USD", currency_locked: false });
        if (path.endsWith("/notifications/preferences")) return json({ preferences: ["calendar", "reservations", "forms", "general"].flatMap(category => ["in_app", "push", "email"].map(channel => ({ category, channel, enabled: true }))) });
        if (path.endsWith("/installations")) return json({ installations: [{ id: "device-1", platform: "windows", display_mode: "browser", is_current: false, last_seen_at: "2026-09-18T00:00:00Z" }] });
        if (path.endsWith("/info")) return json({ user });
        if (path.includes("/projects")) return json({ projects: [], pagination: {} });
        if (path.startsWith("/api/") || url.origin !== origin.origin) return json({ success: true, notifications: [], unread_count: 0, installations: [], preferences: [] });
        return route.continue();
      });
      await page.goto(new URL("/settings", origin).href);
      await expect(page.locator(".settings-tabs")).toBeVisible();
      const tabs = page.getByRole("tab");
      assert.equal(await tabs.count(), 6, "All six settings tabs should be available");
      for (let index = 0; index < 6; index++) {
        await tabs.nth(index).click();
        await expect(tabs.nth(index)).toHaveAttribute("aria-selected", "true");
        await expect(page.getByRole("tabpanel")).toBeVisible();
        await expect(page.locator(".settings-page [role=status]")).toHaveCount(0);
        for (const theme of ["light", "dark"]) {
          await page.evaluate(theme => document.documentElement.dataset.theme = theme, theme);
          const issues = await page.evaluate(() => {
            const root = document.querySelector(".settings-page");
            const bounds = root.getBoundingClientRect();
            const elements = root.querySelectorAll(".settings-tabs, .settings-tab, .settings-card, .settings-profile-summary, .settings-profile-body, .settings-profile-actions, .settings-store-language-card, input:not([type=hidden]):not([type=file]):not([type=checkbox]), textarea, select, button, .device-settings-item, .security-mfa-panel");
            return [...elements].filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== "hidden").flatMap(el => {
              const r = el.getBoundingClientRect();
              const overflow = r.left < bounds.left - 1 || r.right > bounds.right + 1 || r.left < -1 || r.right > innerWidth + 1;
              const clipped = el.matches("button,.settings-tab") && el.clientWidth < el.scrollWidth - 2;
              return overflow || clipped ? [{ element: el.className || el.tagName, left: r.left, right: r.right, client: el.clientWidth, scroll: el.scrollWidth }] : [];
            });
          });
          assert.deepEqual(issues, [], `${width}px ${locale} ${theme} tab ${index}: overflowing or clipped controls`);
          const actionIssues = await page.evaluate(() => [...document.querySelectorAll(".settings-profile-actions")].flatMap(row => {
            const bounds = row.getBoundingClientRect();
            return [...row.querySelectorAll(":scope > button, :scope > a")].flatMap(el => {
              const r = el.getBoundingClientRect();
              return r.left < bounds.left - 1 || r.right > bounds.right + 1 ? [el.className] : [];
            });
          }));
          assert.deepEqual(actionIssues, [], "Action buttons must fit their own row, including padding");
          if (width <= 640) {
            const box = await page.locator(".settings-page").boundingBox();
            assert(box.width >= width - 40, "Mobile settings should use the screen width");
          }
          passed++;
        }
      }
      await page.locator(".security-mfa-enroll-form button").click();
      await expect(page.locator(".security-mfa-verify-flow")).toBeVisible();
      const verifyOverflow = await page.locator(".security-mfa-verify-flow").evaluate(el => [...el.querySelectorAll("input, button, img, code")].filter(el => {
        const r = el.getBoundingClientRect();
        return r.left < -1 || r.right > innerWidth + 1;
      }).map(el => el.className || el.tagName));
      assert.deepEqual(verifyOverflow, [], "Authenticator setup controls must fit");
      await tabs.nth(3).click();
      await page.locator(".device-settings-danger").click();
      await expect(page.getByRole("dialog")).toBeVisible();
      const dialogBox = await page.getByRole("dialog").boundingBox();
      assert(dialogBox.x >= 0 && dialogBox.x + dialogBox.width <= width, "Device dialog must fit the viewport");
      await page.locator(".page-delete-modal-secondary").click();
      assert.deepEqual(errors, [], "No browser exceptions");
      console.log(`PASS all settings tabs ${width}px ${locale}, light and dark`);
      await context.close();
    }
  }
  console.log(`${passed} settings layout checks passed; all API responses mocked.`);
} finally {
  await browser.close();
}
