import { test, expect } from "@playwright/test";
async function provision(page, { aal1 = false, legacy = false, conflict = false } = {}) {
  let held = false, revision = 17, operation = "";
  await page.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (url.origin !== "http://127.0.0.1:5179") return route.abort();
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const json = data => route.fulfill({ json: data });
    if (url.pathname === "/api/auth/user_status") return json({ logged_in: true, user: { id: 7, user_type: "admin", first_name: "Synthetic", email: "synthetic@example.invalid" }, csrf_token: "synthetic-browser-csrf" });
    if (url.pathname === "/api/auth/mfa/status") return json({ factors: [{ id: "synthetic-factor", status: "verified" }] });
    if (url.pathname === "/api/auth/mfa/enroll/verify") { aal1 = false; return json({ success: true }); }
    if (url.pathname.startsWith("/api/admin/billing/")) {
      if (aal1) return route.fulfill({ status: 403, json: { detail: { code: "aal2_required", message: "Verify MFA" } } });
      if (url.pathname.endsWith("price-books")) return json({ price_books: [] });
      if (url.pathname.endsWith("modules/quote")) { const body = route.request().postDataJSON(); return json({ quote: { revision, module_basis: Object.fromEntries(body.module_ids.map(id => [id, { price_book_id: "launch_2026" }])), pricing: { module_ids: body.module_ids, recurring_minor: 3000, currency: "USD", billing_interval: "month", price_groups: [] } } }); }
      if (url.pathname.endsWith("access-history")) return json({ events: operation ? [{ id: "event", operation, actor_user_id: 7, created_at: "2026-09-30T12:00:00Z", result: { revision, previous_state: { revision: revision - 1 }, reason: "Synthetic reason" } }] : [], payments: [], periods: [] });
      if (route.request().method() === "POST") {
        if (conflict) { conflict = false; revision++; return route.fulfill({ status: 409, json: { detail: { code: "commercial_revision_conflict", message: "State changed" } } }); }
        operation = url.pathname.split("/").at(-1); revision++; if (operation === "suspend") held = true; if (operation === "reactivate") held = false;
        return json({ success: true });
      }
      return json({ tenant: { brand_name: "Synthetic browser tenant", owner_name: "Synthetic owner" }, hold: held ? { commercial_suspended_at: "2026-09-30T12:00:00Z", commercial_suspension_reason: "Synthetic reason" } : {}, commercial_access: { revision, access_state: held ? "suspended" : "active", review_state: legacy ? "review_required" : "reviewed" }, entitlements: { assigned_modules: legacy ? [] : ["website"], effective_modules: held ? [] : ["website"], capabilities: [], legacy_assignment_requires_review: legacy, assigned_plan_id: legacy ? "business_plus" : null, pricing: { recurring_minor: 2000, currency: "USD", billing_interval: "month" } } });
    }
    return json({ success: true, notifications: [], unread_count: 0 });
  });
  await page.goto("/admin/tenants/42/commercial");
}
async function confirm(page, name) {
  await page.getByRole("button", { name, exact: true }).click(); await page.getByLabel("Required reason").fill("Synthetic reason"); await page.getByLabel(/I have reviewed/).check(); await page.getByRole("button", { name: "Confirm action" }).click();
}
test("overview, hold, reactivate and durable history in the admin shell", async ({ page }) => {
  await provision(page); await expect(page.getByRole("heading", { name: "Commercial access", exact: true })).toBeVisible(); await confirm(page, "Suspend commercial access"); await expect(page.getByText(/Held since/)).toBeVisible(); await confirm(page, "Reactivate commercial access"); await expect(page.getByText("No administrative hold")).toBeVisible(); await expect(page.getByRole("cell", { name: "reactivate", exact: true })).toBeVisible();
});
test("AAL1 step-up verifies then reloads without mutation replay", async ({ page }) => {
  await provision(page, { aal1: true }); await expect(page.getByRole("heading", { name: "MFA verification required" })).toBeVisible(); await page.getByLabel("Verification code").fill("123456"); await page.getByRole("button", { name: "Verify account" }).click(); await expect(page.getByRole("heading", { name: "Assigned modules & founding basis" })).toBeVisible();
});
test("server quote and assignment refresh", async ({ page }) => {
  await provision(page); await page.getByRole("button", { name: "Manage modules" }).click(); await page.getByRole("checkbox", { name: "Madar Forms", exact: true }).check(); await page.getByLabel("Required reason").fill("Synthetic reason"); await page.getByRole("button", { name: "Preview server quote" }).click(); await expect(page.getByLabel("Server quote")).toContainText("$30.00"); await page.getByLabel(/I have reviewed/).check(); await page.getByRole("button", { name: "Confirm action" }).click(); await expect(page.getByText("18", { exact: true })).toBeVisible();
});
test("stale revision blocks reconfirmation", async ({ page }) => {
  await provision(page, { conflict: true }); await confirm(page, "Suspend commercial access"); await expect(page.getByRole("dialog").getByRole("alert")).toContainText("State refreshed"); await expect(page.getByRole("button", { name: "Confirm action" })).toBeDisabled();
});
test("legacy review and responsive page", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 }); await provision(page, { legacy: true }); await expect(page.getByRole("heading", { name: "Legacy commercial state — Review required" })).toBeVisible(); expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
