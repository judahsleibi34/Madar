import { expect, test } from "@playwright/test";

const authenticatedRoutes = [
  "/dashboard",
  "/page-builder",
  "/page-builder/forms",
  "/builder-responses",
  "/builder-data",
  "/archive",
  "/my-plan",
  "/settings/security",
  "/settings",
  "/notifications",
  "/admin/account-access",
];

async function logIn(page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  const email = page.locator('input[name="email"]');
  const password = page.locator('input[name="password"]');
  await email.fill(process.env.TEST_USER_EMAIL);
  await password.fill(process.env.TEST_USER_PASSWORD);
  const responsePromise = page.waitForResponse(
    (response) => response.url().includes("/auth/login") && response.request().method() === "POST"
  );
  await page.locator('button[type="submit"]').click();
  const response = await responsePromise;
  await email.fill("").catch(() => {});
  await password.fill("").catch(() => {});
  expect(response.ok()).toBeTruthy();
  await page.waitForURL((url) => url.pathname.startsWith("/dashboard"));
}

async function settle(page) {
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  );
}

test("authenticated routes use the shared scales without mini-laptop overflow", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 600 });
  await logIn(page);

  for (const route of authenticatedRoutes) {
    const response = await page.goto(route, { waitUntil: "domcontentloaded", timeout: 30_000 });
    expect(response?.status() || 0, route).toBeLessThan(400);
    await page.locator(".admin-dashboard-layout").waitFor({ state: "visible" });
    await settle(page);

    const result = await page.evaluate(() => {
      const root = document.documentElement;
      const shell = document.querySelector(".admin-dashboard-layout");
      const pageRegion = document.querySelector(".admin-dashboard-page");
      const sidebar = document.querySelector(".admin-sidebar");
      const hamburger = document.querySelector(".dashboard-mobile-menu-button");
      const heading = [...document.querySelectorAll(".builder-brand h1, .admin-dashboard-page h1, .admin-dashboard-page h2")]
        .find((element) => {
          const style = getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
        });
      const headingRect = heading?.getBoundingClientRect();
      const hamburgerRect = hamburger && getComputedStyle(hamburger).display !== "none"
        ? hamburger.getBoundingClientRect()
        : null;
      const pageRect = pageRegion?.getBoundingClientRect();
      const sidebarRect = sidebar?.getBoundingClientRect();
      const shellStyle = getComputedStyle(shell);
      const headingStyle = heading ? getComputedStyle(heading) : null;
      const headingOverlapsMenu = Boolean(
        headingRect && hamburgerRect &&
        headingRect.left < hamburgerRect.right && headingRect.right > hamburgerRect.left &&
        headingRect.top < hamburgerRect.bottom && headingRect.bottom > hamburgerRect.top
      );

      return {
        layoutScale: Number(shellStyle.getPropertyValue("--ui-layout-scale")),
        textScale: Number(shellStyle.getPropertyValue("--ui-text-scale")),
        documentFits: root.scrollWidth <= root.clientWidth + 1,
        pageFits: Boolean(pageRect && pageRect.left >= -1 && pageRect.right <= root.clientWidth + 1),
        closedSidebarOffCanvas: Boolean(sidebarRect && sidebarRect.right <= 1),
        headingFits: !headingRect || (
          headingRect.left >= -1 && headingRect.right <= root.clientWidth + 1 &&
          headingRect.top >= -1 && headingRect.bottom <= window.innerHeight + 1
        ),
        headingOverlapsMenu,
        wordBreak: headingStyle?.wordBreak || "normal",
        overflowWrap: headingStyle?.overflowWrap || "normal",
      };
    });

    expect(result.layoutScale, route).toBeCloseTo(0.67, 3);
    expect(result.textScale, route).toBeCloseTo(0.82, 3);
    expect(result.documentFits, route).toBeTruthy();
    expect(result.pageFits, route).toBeTruthy();
    expect(result.closedSidebarOffCanvas, route).toBeTruthy();
    expect(result.headingFits, route).toBeTruthy();
    expect(result.headingOverlapsMenu, route).toBeFalsy();
    expect(result.wordBreak, route).not.toBe("break-all");
    expect(result.overflowWrap, route).not.toBe("anywhere");
  }
});

test("shared scales update while resizing without navigation or refresh", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await logIn(page);
  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
  await settle(page);

  const navigationCount = await page.evaluate(() => performance.getEntriesByType("navigation").length);
  const initial = await page.locator(".admin-dashboard-layout").evaluate((shell) => ({
    layout: Number(getComputedStyle(shell).getPropertyValue("--ui-layout-scale")),
    text: Number(getComputedStyle(shell).getPropertyValue("--ui-text-scale")),
  }));
  expect(initial.layout).toBeCloseTo(1, 3);
  expect(initial.text).toBeCloseTo(1, 3);

  await page.setViewportSize({ width: 1024, height: 600 });
  await expect(page.locator(".admin-dashboard-layout")).toHaveCSS("--ui-layout-scale", "0.6700");
  const resized = await page.locator(".admin-dashboard-layout").evaluate((shell) => ({
    layout: Number(getComputedStyle(shell).getPropertyValue("--ui-layout-scale")),
    text: Number(getComputedStyle(shell).getPropertyValue("--ui-text-scale")),
  }));
  expect(resized.layout).toBeCloseTo(0.67, 3);
  expect(resized.text).toBeCloseTo(0.82, 3);
  expect(await page.evaluate(() => performance.getEntriesByType("navigation").length)).toBe(navigationCount);
  expect(new URL(page.url()).pathname).toBe("/dashboard");
});

test("existing navigation drawer and builder modal remain viewport-contained", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 600 });
  await logIn(page);
  await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
  await page.locator(".dashboard-mobile-menu-button").click();
  await expect(page.locator(".admin-dashboard-layout")).toHaveClass(/sidebar-open/);
  await expect(page.locator(".admin-sidebar")).toBeVisible();
  await page.waitForTimeout(300);
  const drawer = await page.locator(".admin-sidebar").boundingBox();
  expect(drawer?.x).toBeGreaterThanOrEqual(-1);
  expect((drawer?.x || 0) + (drawer?.width || 0)).toBeLessThanOrEqual(1025);
  expect((drawer?.y || 0) + (drawer?.height || 0)).toBeLessThanOrEqual(601);
  await page.locator(".dashboard-sidebar-backdrop").click({ position: { x: 1000, y: 580 } });

  await page.goto("/page-builder", { waitUntil: "domcontentloaded" });
  await page.locator(".builder-layout").waitFor({ state: "visible" });
  await page.locator(".page-action-stack button", { hasText: "Templates" }).click();
  const modal = page.locator(".builder-modal:visible, .template-picker-modal:visible").first();
  await expect(modal).toBeVisible();
  const modalBox = await modal.boundingBox();
  expect(modalBox?.x).toBeGreaterThanOrEqual(-1);
  expect((modalBox?.x || 0) + (modalBox?.width || 0)).toBeLessThanOrEqual(1025);
  expect(modalBox?.y).toBeGreaterThanOrEqual(-1);
  expect((modalBox?.y || 0) + (modalBox?.height || 0)).toBeLessThanOrEqual(601);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBeTruthy();
});
