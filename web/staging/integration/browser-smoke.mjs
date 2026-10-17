// Run only through a verified loopback tunnel to the dedicated staging VM.
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { readFileSync, statSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(new URL("../../frontend/package.json", import.meta.url));
const { chromium } = require("@playwright/test");
assert.equal(process.env.MADAR_STAGING_BROWSER_HOST, "madar-staging", "Verify the SSH tunnel destination first");
const path = process.argv[2];
assert.equal(statSync(path).mode & 0o777, 0o600, "Synthetic fixture must be private");
const fixture = JSON.parse(readFileSync(path, "utf8"));
assert.match(fixture.admin_email, /^hardening-[a-f0-9]{16}@example\.com$/);

function totp(secret) {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const character of secret.replace(/=+$/, "").toUpperCase()) {
    const value = alphabet.indexOf(character);
    assert.ok(value >= 0);
    bits += value.toString(2).padStart(5, "0");
  }
  const key = Buffer.from(bits.match(/.{8}/g).map(byte => parseInt(byte, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const digest = createHmac("sha1", key).update(counter).digest();
  const offset = digest[digest.length - 1] & 15;
  return ((digest.readUInt32BE(offset) & 0x7fffffff) % 1000000).toString().padStart(6, "0");
}

const browser = await chromium.launch({
  headless: true,
  ...(process.env.MADAR_STAGING_CHROMIUM ? { executablePath: process.env.MADAR_STAGING_CHROMIUM } : {}),
});
const baseURL = "https://127.0.0.1:18443";
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, ignoreHTTPSErrors: true });
  const blockedExternalHosts = new Set();
  await context.route("**/*", route => {
    const url = new URL(route.request().url());
    if (["127.0.0.1", "localhost"].includes(url.hostname) || ["data:", "blob:"].includes(url.protocol)) return route.continue();
    blockedExternalHosts.add(url.hostname);
    return route.abort();
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", () => errors.push("pageerror"));
  await page.goto(baseURL + "/login");
  await page.locator('input[type="email"]').fill(fixture.admin_email);
  await page.locator('input[name="password"]').fill(fixture.admin_password);
  await page.locator('form.login-card button[type="submit"]').click();
  await page.locator('input[autocomplete="one-time-code"]').waitFor({ state: "visible", timeout: 20000 });
  const pending = await context.cookies(baseURL);
  assert.ok(pending.some(cookie => cookie.name === "madar_mfa_pending" && cookie.httpOnly && cookie.secure));
  assert.ok(!pending.some(cookie => cookie.name === "madar_access_token"));
  const remaining = 30000 - Date.now() % 30000;
  if (remaining < 5000) await new Promise(resolve => setTimeout(resolve, remaining + 100));
  await page.locator('input[autocomplete="one-time-code"]').fill(totp(fixture.mfa_secret));
  const verification = page.waitForResponse(response => response.url().endsWith("/api/auth/mfa/login/verify"));
  await page.locator('form.login-card button[type="submit"]').click();
  assert.equal((await verification).status(), 200);
  await page.waitForURL(url => !url.pathname.includes("login"), { timeout: 20000 });
  const ordinary = await context.cookies(baseURL);
  for (const name of ["madar_access_token", "madar_refresh_token"]) {
    const cookie = ordinary.find(item => item.name === name);
    assert.ok(cookie?.httpOnly && cookie.secure && cookie.sameSite === "Lax");
  }
  assert.ok(!ordinary.some(cookie => cookie.name === "madar_mfa_pending"));
  assert.ok(!(await page.evaluate(() => document.cookie)).includes("madar_access_token="));
  assert.equal(await page.evaluate(async () => (await fetch("/api/admin/users", { credentials: "include" })).status), 200);
  const desktopPath = new URL(page.url()).pathname;
  await context.close();
  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, ignoreHTTPSErrors: true });
  const mobilePage = await mobile.newPage();
  await mobilePage.goto(baseURL + "/login");
  const email = mobilePage.locator('input[type="email"]');
  await email.waitFor({ state: "visible" });
  assert.ok(await email.evaluate(element => element.labels.length > 0));
  await email.focus();
  await mobilePage.keyboard.press("Tab");
  assert.notEqual(await mobilePage.evaluate(() => document.activeElement.tagName), "BODY");
  assert.ok(await mobilePage.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 2));
  await mobile.close();
  assert.equal(errors.length, 0);
  console.log(JSON.stringify({ status: "PASS", browser: browser.version(), desktopPath,
    checks: ["password-to-restricted-MFA", "native-TOTP-admission", "admin-page-and-API", "Secure-HttpOnly-SameSite-cookies",
      "pending-cookie-removal", "script-cannot-read-access-cookie", "mobile-login-label-keyboard-and-width"],
    blockedExternalHostCount: blockedExternalHosts.size, pageErrors: errors.length }));
} finally {
  await browser.close();
}
