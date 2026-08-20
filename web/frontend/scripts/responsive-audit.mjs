import { mkdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { chromium } from "@playwright/test";

const baseUrl = process.env.RESPONSIVE_AUDIT_URL || "http://127.0.0.1:5173";
const outputDir = path.join(os.tmpdir(), "madar-responsive-audit");

const viewports = [
  [1920, 1080],
  [1680, 1050],
  [1600, 900],
  [1536, 864],
  [1440, 900],
  [1440, 810],
  [1366, 768],
  [1280, 800],
  [1280, 720],
  [1024, 768],
  [768, 1024],
  [390, 844],
];

const screenshotViewports = new Set([
  "1536x864",
  "1366x768",
  "1280x800",
  "1280x720",
  "1024x768",
  "768x1024",
  "390x844",
]);

const publicRoutes = [
  "/",
  "/demo",
  "/pricing",
  "/pricing/base-plans",
  "/pricing/custom-plan",
  "/team",
  "/about",
  "/contact",
  "/privacy-policy",
  "/terms-and-conditions",
  "/login",
  "/signup",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/site/responsive-audit",
];

const adminRoutes = [
  "/dashboard",
  "/admin/users",
  "/admin/account-access",
  "/notifications",
  "/page-builder",
  "/builder-responses",
  "/builder-data",
  "/archive",
  "/my-plan",
  "/settings/security",
  "/settings",
];

const userRoutes = [
  "/dashboard",
  "/page-builder/form-preview/responsive-audit",
  "/page-builder/preview",
  "/page-builder",
  "/builder-responses",
  "/builder-data",
  "/archive",
  "/my-plan",
  "/notifications",
  "/settings/change-password",
  "/settings/security",
  "/settings",
];

const screenshotRoutes = new Set([
  "/",
  "/login",
  "/signup",
  "/pricing/base-plans",
  "/dashboard",
  "/page-builder",
  "/builder-responses",
  "/builder-data",
  "/settings",
]);

const fakeUser = (userType) => ({
  id: userType === "admin" ? 9001 : 9002,
  auth_id: `responsive-audit-${userType}`,
  tenant_id: 901,
  first_name: "Responsive",
  last_name: "Audit",
  name: "Responsive Audit",
  email: `${userType}@responsive-audit.invalid`,
  phone: "",
  avatar: "",
  subscription_type: "pro",
  plan: "pro",
  builder_type: "website",
  features: [],
  payment_status: "active",
  user_type: userType,
});

const safeName = (value) =>
  value.replace(/^\/+/, "").replace(/[^a-z0-9]+/gi, "-") || "home";

async function installAuthMock(page, userType) {
  const user = fakeUser(userType);

  await page.route("**/api/auth/user_status**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ logged_in: true, authenticated: true, user }),
    });
  });
}

async function inspectPage(page) {
  return page.evaluate(() => {
    const root = document.documentElement;
    const viewportWidth = root.clientWidth;
    const viewportHeight = window.innerHeight;
    const globallyOverflowing = root.scrollWidth > viewportWidth + 1;
    const offenders = [];
    const clippedFixedControls = [];

    for (const element of document.querySelectorAll("body *")) {
      const style = getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden") continue;

      const rect = element.getBoundingClientRect();
      if (rect.width > viewportWidth + 1 || rect.right > viewportWidth + 2 || rect.left < -2) {
        offenders.push({
          tag: element.tagName.toLowerCase(),
          className: String(element.className || "").slice(0, 140),
          left: Math.round(rect.left),
          right: Math.round(rect.right),
          width: Math.round(rect.width),
          overflowX: style.overflowX,
        });
      }

      if (
        style.position === "fixed" &&
        (element.matches("button, a, input, select, textarea") || element.querySelector("button, a, input, select, textarea")) &&
        (rect.bottom < 0 || rect.top > viewportHeight || rect.right < 0 || rect.left > viewportWidth)
      ) {
        const isClosedDashboardDrawer =
          element.matches(".admin-sidebar") &&
          !document.querySelector(".admin-dashboard-layout.sidebar-open");

        if (isClosedDashboardDrawer) continue;

        clippedFixedControls.push({
          tag: element.tagName.toLowerCase(),
          className: String(element.className || "").slice(0, 140),
        });
      }

      if (offenders.length >= 12 && clippedFixedControls.length >= 6) break;
    }

    return {
      globallyOverflowing,
      clientWidth: viewportWidth,
      scrollWidth: root.scrollWidth,
      scrollHeight: root.scrollHeight,
      offenders: offenders.slice(0, 12),
      clippedFixedControls: clippedFixedControls.slice(0, 6),
    };
  });
}

async function auditRouteSet(browser, routeSet, role) {
  const results = [];

  for (const [width, height] of viewports) {
    const viewportName = `${width}x${height}`;
    const context = await browser.newContext({ viewport: { width, height } });
    const page = await context.newPage();
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));

    if (role) await installAuthMock(page, role);

    for (let routeIndex = 0; routeIndex < routeSet.length; routeIndex += 1) {
      const route = routeSet[routeIndex];
      const response = await page.goto(`${baseUrl}${route}`, {
        waitUntil: "domcontentloaded",
        timeout: 30_000,
      });
      if (routeIndex === 0) await page.waitForTimeout(900);
      await page.waitForTimeout(350);

      const layout = await inspectPage(page);
      const result = {
        role: role || "public",
        route,
        viewport: viewportName,
        status: response?.status() || 0,
        finalPath: new URL(page.url()).pathname,
        ...layout,
        pageErrors: [...pageErrors],
      };
      results.push(result);
      pageErrors.length = 0;

      if (screenshotViewports.has(viewportName) && screenshotRoutes.has(route)) {
        await page.screenshot({
          path: path.join(outputDir, `${role || "public"}-${safeName(route)}-${viewportName}.png`),
          fullPage: false,
        });
      }
    }

    await context.close();
  }

  return results;
}

await mkdir(outputDir, { recursive: true });

const browser = await chromium.launch({ channel: "chrome", headless: true });
const results = [
  ...(await auditRouteSet(browser, publicRoutes, null)),
  ...(await auditRouteSet(browser, adminRoutes, "admin")),
  ...(await auditRouteSet(browser, userRoutes, "user")),
];
await browser.close();

const failures = results.filter(
  (result) =>
    result.globallyOverflowing ||
    result.clippedFixedControls.length > 0
);

const applicationErrors = results.filter((result) => result.pageErrors.length > 0);

const report = {
  generatedAt: new Date().toISOString(),
  baseUrl,
  outputDir,
  routeChecks: results.length,
  failureCount: failures.length,
  applicationErrorCount: applicationErrors.length,
  failures,
  applicationErrors,
};

await writeFile(
  path.join(outputDir, "report.json"),
  `${JSON.stringify(report, null, 2)}\n`,
  "utf8"
);

console.log(JSON.stringify({
  outputDir,
  routeChecks: report.routeChecks,
  failureCount: report.failureCount,
  applicationErrorCount: report.applicationErrorCount,
}, null, 2));

if (failures.length > 0) process.exitCode = 1;
