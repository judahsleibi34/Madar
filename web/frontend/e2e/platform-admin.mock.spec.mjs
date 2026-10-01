import { test, expect } from "@playwright/test";

async function provision(page, { level = "aal2", readChallenge = false, mutationChallenge = false, login = false, noFactor = false, failUsers = false, tenant = false } = {}) {
  let reads = 0, mutations = 0, tenantCalls = 0;
  let authenticated = !login;
  const user = { id: 7, tenant_id: 42, account_kind: "platform", user_type: tenant ? "user" : "admin", first_name: "Synthetic", email: "synthetic@example.invalid" };
  await page.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (url.origin !== "http://127.0.0.1:5179") return route.abort();
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const path = url.pathname, method = route.request().method();
    const json = data => route.fulfill({ json: data });
    const denied = () => route.fulfill({ status: 403, json: { detail: { code: "aal2_required", message: "Verify MFA" } } });
    if (/\/(notifications|installations|screen-time)(\/|$)/.test(path)) { tenantCalls++; return json({ notifications: [], unread_count: 0, seconds: 0 }); }
    if (path === "/api/auth/user_status") return json({ logged_in: authenticated, user: authenticated ? user : null, csrf_token: "synthetic-browser-csrf" });
    if (path === "/api/auth/refresh") return json({ logged_in: authenticated, user: authenticated ? user : null });
    if (path === "/api/auth/login") return json(noFactor ? { mfa_enrollment_required: true } : { mfa_required: true, factors: [{ id: "factor", status: "verified" }] });
    if (path === "/api/auth/mfa/login/challenge") return json({ challenge_id: "challenge" });
    if (path === "/api/auth/mfa/login/enroll") return json({ factor: { id: "factor" }, totp: { uri: "otpauth://totp/synthetic" } });
    if (path.endsWith("/verify") && path.includes("/auth/mfa/")) { level = "aal2"; authenticated = true; return json({ success: true, user, csrf_token: "synthetic-browser-csrf" }); }
    if (path === "/api/auth/mfa/status") return json({ mfa_required: !tenant, aal: { current_level: level }, factors: noFactor ? [] : [{ id: "factor", status: "verified", factor_type: "totp" }] });
    if (path.startsWith("/api/admin/users")) {
      if (method === "PATCH" || method === "DELETE") { mutations++; if (mutationChallenge && mutations === 1) { level = "aal1"; return denied(); } return json({ success: true }); }
      reads++;
      if (failUsers) return route.fulfill({ status: 503, json: { detail: "Unavailable" } });
      if (readChallenge && reads === 1) { level = "aal1"; return denied(); }
      return json({ users: [{ id: 12, first_name: "Actual", email: "actual@example.invalid", tenant_id: 42, user_type: "user" }], pagination: { total_count: 1, page: 1 } });
    }
    return json({ success: true, projects: [], pages: [], data: [] });
  });
  return { reads: () => reads, mutations: () => mutations, tenantCalls: () => tenantCalls };
}
async function verify(page) {
  await page.getByLabel("Verification code").fill("123456");
  await page.getByRole("button", { name: "Verify account" }).click();
}
test("login requires MFA before dashboard and enforces background isolation", async ({ page }) => {
  const counts = await provision(page, { login: true, level: "aal1" });
  await page.goto("/login"); await page.getByLabel("Email", { exact: true }).fill("synthetic@example.invalid"); await page.getByLabel("Password", { exact: true }).fill("synthetic-password"); await page.getByRole("button", { name: "Log In", exact: true }).click();
  await expect(page.locator(".admin-layout")).toHaveCount(0);
  await page.locator('input[autocomplete="one-time-code"]').fill("123456");
  await page.locator('button[type="submit"]').click();
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  await page.clock.install(); await page.clock.runFor(70000);
  expect(counts.tenantCalls()).toBe(0);
});
test("restricted login enrollment can establish AAL2 without privileged content", async ({ page }) => {
  await provision(page, { login: true, noFactor: true, level: "aal1" });
  await page.goto("/login"); await page.getByLabel("Email", { exact: true }).fill("synthetic@example.invalid"); await page.getByLabel("Password", { exact: true }).fill("synthetic-password"); await page.getByRole("button", { name: "Log In", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Administrator MFA enrollment required" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Set up authenticator" }).click(); await verify(page);
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
});
test("direct users route cannot bypass AAL1 gate", async ({ page }) => {
  const counts = await provision(page, { level: "aal1" }); await page.goto("/admin/users");
  await expect(page.getByRole("heading", { name: "MFA verification required" })).toBeVisible(); expect(counts.reads()).toBe(0);
  await expect(page.getByText("Actual", { exact: true })).toHaveCount(0);
  await verify(page); await expect(page.getByText("Actual", { exact: true })).toBeVisible();
});
test("users read challenge retries once", async ({ page }) => {
  const counts = await provision(page, { readChallenge: true }); await page.goto("/admin/users"); await verify(page);
  await expect(page.getByText("Actual", { exact: true })).toBeVisible(); expect(counts.reads()).toBe(2);
});
test("users mutation cannot replay after verification", async ({ page }) => {
  const counts = await provision(page, { mutationChallenge: true }); await page.goto("/admin/users");
  await page.getByRole("combobox", { name: "Role", exact: true }).selectOption("admin"); await page.getByRole("button", { name: "Save role" }).click(); await verify(page);
  await expect(page.getByRole("combobox", { name: "Role", exact: true })).toHaveValue("user"); expect(counts.mutations()).toBe(1);
  await page.getByRole("combobox", { name: "Role", exact: true }).selectOption("admin"); await page.getByRole("button", { name: "Save role" }).click();
  await expect.poll(counts.mutations).toBe(2);
});
for (const width of [1440, 390]) test(`platform sidebar and truthful dashboard at ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 844 }); const counts = await provision(page); await page.goto("/dashboard");
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  if (width === 390) await page.getByRole("button", { name: "Open menu" }).click();
  const nav = page.getByRole("navigation", { name: "Dashboard navigation" });
  for (const name of ["Dashboard", "Users / Tenants", "Account Access", "Security"]) await expect(nav.getByRole("button", { name, exact: true })).toBeVisible();
  for (const name of ["Workspace", "Online Store", "My Plan", "CV Rerank", "Home"]) await expect(nav.getByRole("button", { name, exact: true })).toHaveCount(0);
  for (const fake of ["4,862", "$62.4K", "99.98%", "1,284", "6,420", "142ms", "18"]) await expect(page.getByText(fake, { exact: true })).toHaveCount(0);
  await expect(page.getByText(/Not available/)).toHaveCount(3);
  expect(counts.tenantCalls()).toBe(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
test("users source failure cannot masquerade as empty list", async ({ page }) => {
  await provision(page, { failUsers: true }); await page.goto("/admin/users"); await expect(page.getByRole("heading", { name: "User Management" })).toBeVisible();
  await expect(page.locator(".user-management-stats")).toHaveCount(0); await expect(page.locator(".user-management-empty")).toHaveCount(0);
});

test("tenant workspace still starts appropriate background services", async ({ page }) => {
  const counts = await provision(page, { tenant: true }); await page.goto("/dashboard");
  await expect.poll(counts.tenantCalls).toBeGreaterThan(0);
});
test("platform notification URL redirects without mounting tenant services", async ({ page }) => {
  const counts = await provision(page); await page.goto("/notifications");
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  expect(counts.tenantCalls()).toBe(0);
});

test("real FastAPI cookie jar: primary login, challenge, verify and admin admission", async ({ page, context }) => {
  test.skip(!process.env.MADAR_MFA_COOKIE_FIXTURE_COMMAND, "Requires the locked loopback-only FastAPI cookie fixture");
  let challengeCookie = "", pendingHeaders = [];
  await page.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (url.origin !== "http://127.0.0.1:5179") return route.abort();
    if (!url.pathname.startsWith("/api/")) return route.continue();
    if (url.pathname.startsWith("/api/auth/")) {
      if (url.pathname.endsWith("/login/challenge")) challengeCookie = await route.request().headerValue("cookie") || "";
      const response = await route.fetch({ url: "http://127.0.0.1:18091" + url.pathname.slice(4) });
      if (url.pathname === "/api/auth/login") pendingHeaders = response.headersArray().filter(header => header.name.toLowerCase() === "set-cookie");
      return route.fulfill({ response });
    }
    if (url.pathname.startsWith("/api/admin/users")) return route.fulfill({ json: { users: [], pagination: { total_count: 0 } } });
    return route.fulfill({ status: 403, json: { detail: "Unexpected tenant endpoint" } });
  });
  await page.goto("/login"); await page.getByLabel("Email", { exact: true }).fill("synthetic@example.com"); await page.getByLabel("Password", { exact: true }).fill("synthetic-password"); await page.getByRole("button", { name: "Log In", exact: true }).click();
  await expect(page.locator('input[autocomplete="one-time-code"]')).toBeVisible();
  const before = await context.cookies();
  expect(before.some(cookie => cookie.name === "madar_mfa_pending" && cookie.httpOnly && cookie.path === "/")).toBe(true);
  expect(before.some(cookie => cookie.name === "madar_access_token" || cookie.name === "madar_refresh_token")).toBe(false);
  expect(pendingHeaders.some(header => header.value.includes("madar_mfa_pending=") && header.value.includes("Max-Age=300"))).toBe(true);
  await page.getByRole("button", { name: "Back to login", exact: true }).click();
  await expect(page.getByRole("button", { name: "Log In", exact: true })).toBeVisible();
  expect((await context.cookies()).some(cookie => cookie.name === "madar_mfa_pending")).toBe(false);
  await page.getByRole("button", { name: "Log In", exact: true }).click();
  await expect(page.locator('input[autocomplete="one-time-code"]')).toBeVisible();
  await page.locator('input[autocomplete="one-time-code"]').fill("000000"); await page.locator('button[type="submit"]').click();
  await expect(page.getByText("Could not verify MFA code", { exact: true }).first()).toBeVisible();
  expect((await context.cookies()).some(cookie => cookie.name === "madar_access_token")).toBe(false);
  expect((await context.cookies()).some(cookie => cookie.name === "madar_mfa_pending")).toBe(true);
  await page.locator('input[autocomplete="one-time-code"]').fill("123456"); await page.locator('button[type="submit"]').click();
  await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  expect(challengeCookie).toContain("madar_mfa_pending=");
  const after = await context.cookies();
  expect(after.some(cookie => cookie.name === "madar_mfa_pending")).toBe(false);
  expect(after.some(cookie => cookie.name === "madar_access_token" && cookie.httpOnly)).toBe(true);
});
