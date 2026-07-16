import { expect, test } from "@playwright/test";

const authenticatedRoutes = [
  "/dashboard",
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

const requiredViewports = [
  [1920, 1080],
  [1600, 900],
  [1536, 864],
  [1440, 900],
  [1366, 768],
  [1280, 720],
  [1146, 870],
  [1024, 768],
  [1024, 600],
  [768, 1024],
  [430, 932],
  [390, 844],
  [360, 800],
  [320, 568],
];

async function logIn(page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  const email = page.locator('input[name="email"]');
  const password = page.locator('input[name="password"]');
  await email.fill(process.env.TEST_USER_EMAIL);
  await password.fill(process.env.TEST_USER_PASSWORD);

  const loginResponse = page.waitForResponse(
    (response) => response.url().includes("/auth/login") && response.request().method() === "POST",
  );
  await page.locator('button[type="submit"]').click();
  const response = await loginResponse;
  await email.fill("").catch(() => {});
  await password.fill("").catch(() => {});
  if (!response.ok()) throw new Error(`Dedicated test-account login failed (${response.status()}).`);
  await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), { timeout: 20_000 });
}

async function clearAuthentication(page) {
  try {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
    const logout = page.locator(".desktop-navigation-sidebar .admin-sidebar-logout");
    if (await logout.isVisible().catch(() => false)) {
      await logout.click();
      await page.waitForURL((url) => url.pathname === "/", { timeout: 20_000 });
    }
  } finally {
    await page.context().clearCookies();
    await page.goto("/login", { waitUntil: "domcontentloaded" }).catch(() => {});
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    }).catch(() => {});
  }
}

test("shared authenticated navigation is consistent on every user route", async ({ page }) => {
  await logIn(page);

  try {
    for (const route of authenticatedRoutes) {
      await page.goto(route, { waitUntil: "domcontentloaded" });
      await page.locator(".admin-dashboard-layout").waitFor({ state: "visible", timeout: 30_000 });

      for (const [width, height] of requiredViewports) {
        await page.setViewportSize({ width, height });
        await page.waitForTimeout(80);

        const shell = page.locator(".admin-dashboard-layout");
        const desktopSidebar = page.locator(".desktop-navigation-sidebar");
        const trigger = page.locator(".responsive-navigation-trigger");
        const drawer = page.locator(".responsive-navigation-drawer");
        const main = page.locator(".admin-dashboard-page");

        if (width >= 1440) {
          await expect(desktopSidebar, `${route} desktop sidebar at ${width}x${height}`).toBeVisible();
          await expect(trigger).toBeHidden();
          await expect(drawer).toBeHidden();
          const sidebarBox = await desktopSidebar.boundingBox();
          expect(sidebarBox?.width).toBeGreaterThanOrEqual(68);
          expect(sidebarBox?.width).toBeLessThanOrEqual(265);
          await expect(desktopSidebar.locator(".admin-sidebar-nav")).toHaveCSS("flex-direction", "column");
          expect(await desktopSidebar.locator('[aria-current="page"]').count()).toBe(1);
          continue;
        }

        await expect(desktopSidebar, `${route} persistent sidebar at ${width}x${height}`).toBeHidden();
        await expect(trigger).toBeVisible();
        const closedMainBox = await main.boundingBox();
        expect(closedMainBox?.x).toBeLessThanOrEqual(1);
        expect(closedMainBox?.width).toBeGreaterThanOrEqual(width - 1);

        if (route === "/dashboard" && width === 1146 && height === 870) {
          const cards = page.locator(".user-dashboard-summary .user-dashboard-stat");
          expect(await cards.count()).toBeGreaterThan(0);
          const cardWidths = await cards.evaluateAll((elements) =>
            elements.map((element) => element.getBoundingClientRect().width),
          );
          expect(Math.min(...cardWidths)).toBeGreaterThanOrEqual(220);

          const workspacePlan = page.locator(".user-dashboard-stat div > span", {
            hasText: "Workspace plan",
          });
          await expect(workspacePlan).toBeVisible();
          const workspaceTextLayout = await workspacePlan.evaluate((element) => {
            const style = getComputedStyle(element);
            const rect = element.getBoundingClientRect();
            return {
              height: rect.height,
              lineHeight: Number.parseFloat(style.lineHeight),
              overflowWrap: style.overflowWrap,
              wordBreak: style.wordBreak,
            };
          });
          expect(workspaceTextLayout.wordBreak).toBe("normal");
          expect(workspaceTextLayout.overflowWrap).toBe("normal");
          expect(workspaceTextLayout.height).toBeLessThanOrEqual(workspaceTextLayout.lineHeight * 2.2);
          expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
          await page.screenshot({ path: "test-results/dashboard-1146x870.png", fullPage: false });
        }

        await trigger.click();
        await expect(shell).toHaveClass(/sidebar-open/);
        await expect(drawer).toBeVisible();
        const drawerBox = await drawer.boundingBox();
        expect(drawerBox?.x).toBeGreaterThanOrEqual(-1);
        expect((drawerBox?.x || 0) + (drawerBox?.width || 0)).toBeLessThanOrEqual(width + 1);

        const navigation = drawer.locator(".admin-sidebar-nav");
        const navigationLayout = await navigation.evaluate((element) => {
          const style = getComputedStyle(element);
          return { display: style.display, direction: style.flexDirection };
        });
        expect(navigationLayout).toEqual({ display: "flex", direction: "column" });

        const visibleLabels = await navigation.locator("button > span, a > span").evaluateAll(
          (labels) => labels.filter((label) => label.getClientRects().length > 0).length,
        );
        expect(visibleLabels).toBeGreaterThanOrEqual(5);
        expect(await drawer.locator('[aria-current="page"]').count()).toBe(1);

        const accountAndActions = await drawer.evaluate((element) => {
          const account = element.querySelector(".admin-sidebar-user");
          const actions = element.querySelector(".admin-sidebar-final-actions");
          return {
            accountBeforeActions: Boolean(
              account &&
              actions &&
              account.compareDocumentPosition(actions) & Node.DOCUMENT_POSITION_FOLLOWING
            ),
            actionColumns: actions
              ? getComputedStyle(actions).gridTemplateColumns.split(" ").length
              : 0,
            overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
          };
        });
        expect(accountAndActions.accountBeforeActions).toBe(true);
        expect(accountAndActions.actionColumns).toBe(3);
        expect(accountAndActions.overflow).toBe(false);

        const drawerText = (await drawer.innerText()).toLowerCase();
        for (const builderOnlyText of ["editing tools", "current page", "save changes", "go live", "preview site"]) {
          expect(drawerText).not.toContain(builderOnlyText);
        }

        const openMainBox = await main.boundingBox();
        expect(Math.abs((openMainBox?.width || 0) - (closedMainBox?.width || 0))).toBeLessThanOrEqual(2);
        if (width === 1146) {
          await page.locator(".responsive-navigation-backdrop").click({ position: { x: width - 8, y: 8 } });
        } else {
          await page.keyboard.press("Escape");
        }
        await expect(shell).not.toHaveClass(/sidebar-open/);
        await expect(trigger).toBeFocused();
      }
    }
  } finally {
    await clearAuthentication(page);
  }
});

test("dynamic resizing releases and restores authenticated shell width", async ({ page }) => {
  await logIn(page);

  try {
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
    await page.locator(".admin-dashboard-layout").waitFor({ state: "visible", timeout: 30_000 });

    for (const [width, height, desktopExpected] of [
      [1536, 864, true],
      [1146, 870, false],
      [1024, 768, false],
      [1146, 870, false],
      [1536, 864, true],
    ]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(100);

      const desktopSidebar = page.locator(".desktop-navigation-sidebar");
      const trigger = page.locator(".responsive-navigation-trigger");
      const main = page.locator(".admin-dashboard-page");

      if (desktopExpected) {
        await expect(desktopSidebar).toBeVisible();
        await expect(trigger).toBeHidden();
      } else {
        await expect(desktopSidebar).toBeHidden();
        await expect(trigger).toBeVisible();
        const mainBox = await main.boundingBox();
        expect(mainBox?.x).toBeLessThanOrEqual(1);
        expect(mainBox?.width).toBeGreaterThanOrEqual(width - 1);
      }

      const cardWidths = await page.locator(".user-dashboard-summary .user-dashboard-stat").evaluateAll(
        (elements) => elements.map((element) => element.getBoundingClientRect().width),
      );
      expect(cardWidths.every((cardWidth) => cardWidth >= 220)).toBe(true);
      expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
    }
  } finally {
    await clearAuthentication(page);
  }
});