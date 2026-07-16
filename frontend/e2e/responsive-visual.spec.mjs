import path from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test } from "@playwright/test";

const specDirectory = path.dirname(fileURLToPath(import.meta.url));
const screenshotDirectory = path.resolve(
  specDirectory,
  "../test-results/responsive-visual"
);

const check = (issues, condition, message) => {
  if (!condition) issues.push(message);
};

const inside = (inner, outer, tolerance = 1) =>
  Boolean(
    inner &&
      outer &&
      inner.x >= outer.x - tolerance &&
      inner.y >= outer.y - tolerance &&
      inner.x + inner.width <= outer.x + outer.width + tolerance &&
      inner.y + inner.height <= outer.y + outer.height + tolerance
  );

const overlaps = (first, second, tolerance = 1) =>
  Boolean(
    first &&
      second &&
      first.x < second.x + second.width - tolerance &&
      first.x + first.width > second.x + tolerance &&
      first.y < second.y + second.height - tolerance &&
      first.y + first.height > second.y + tolerance
  );

async function maskDedicatedIdentity(page) {
  await page.evaluate((identity) => {
    const normalizedIdentity = String(identity || "").trim().toLowerCase();
    if (!normalizedIdentity) return;

    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const textNodes = [];
    while (walker.nextNode()) textNodes.push(walker.currentNode);
    for (const node of textNodes) {
      if (String(node.nodeValue || "").toLowerCase().includes(normalizedIdentity)) {
        node.nodeValue = "Dedicated test account";
      }
    }

    for (const input of document.querySelectorAll("input")) {
      if (String(input.value || "").toLowerCase().includes(normalizedIdentity)) {
        input.value = "";
      }
    }
  }, process.env.TEST_USER_EMAIL);
}

async function capture(page, filename) {
  await maskDedicatedIdentity(page);
  await page.screenshot({
    path: path.join(screenshotDirectory, filename),
    fullPage: false,
  });
}

async function logIn(page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });
  const emailInput = page.locator('input[name="email"]');
  const passwordInput = page.locator('input[name="password"]');
  await emailInput.waitFor({ state: "visible" });
  await passwordInput.waitFor({ state: "visible" });
  await emailInput.fill(process.env.TEST_USER_EMAIL);
  await passwordInput.fill(process.env.TEST_USER_PASSWORD);

  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/auth/login") && response.request().method() === "POST"
  );
  await page.locator('button[type="submit"]').click();
  const response = await responsePromise;
  await emailInput.fill("").catch(() => {});
  await passwordInput.fill("").catch(() => {});
  if (!response.ok()) throw new Error(`Dedicated test-account login failed (${response.status()}).`);
  await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), {
    timeout: 20_000,
  });
}

async function neutralizeSession(page, issues) {
  try {
    await page.setViewportSize({ width: 1366, height: 800 });
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
    const logout = page.locator(".desktop-navigation-sidebar .admin-sidebar-logout");
    if (!(await logout.isVisible().catch(() => false))) {
      const navigationToggle = page.locator(".dashboard-mobile-menu-button");
      if (await navigationToggle.isVisible().catch(() => false)) {
        await navigationToggle.click();
      }
    }
    await logout.waitFor({ state: "visible", timeout: 10_000 });
    await logout.click();
    await page.waitForURL((url) => url.pathname === "/", { timeout: 20_000 });
  } catch {
    issues.push("The visual-audit session did not log out through the application.");
  } finally {
    await page.context().clearCookies();
    await page.goto("/login", { waitUntil: "domcontentloaded" }).catch(() => {});
    await page
      .evaluate(() => {
        localStorage.clear();
        sessionStorage.clear();
      })
      .catch(() => {});
    await page.reload({ waitUntil: "domcontentloaded" }).catch(() => {});
    await page.locator('input[name="email"]').fill("").catch(() => {});
    await page.locator('input[name="password"]').fill("").catch(() => {});
  }
}

async function findTinyScrollRegions(page, rootSelector) {
  return page.evaluate((selector) => {
    const root = document.querySelector(selector);
    if (!root) return ["missing-root"];
    return [...root.querySelectorAll("*")]
      .filter((element) => {
        const style = getComputedStyle(element);
        const scrolls = ["auto", "scroll"].includes(style.overflowY);
        return scrolls && element.scrollHeight > element.clientHeight + 2 && element.clientHeight < 80;
      })
      .map((element) => String(element.className || element.tagName).slice(0, 90));
  }, rootSelector);
}

async function settleResponsiveLayout(page) {
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  );
}

async function openCompactMenu(page, menuClass) {
  const root = page.locator(`.${menuClass}`);
  const trigger = root.locator(":scope > button");
  await trigger.click();
  const menu = root.locator('[role="menu"]');
  await menu.waitFor({ state: "visible" });
  return { menu, root, trigger };
}

async function chooseCompactMenuItem(page, menuClass, label) {
  const { menu } = await openCompactMenu(page, menuClass);
  await menu.locator('[role^="menuitem"]', { hasText: new RegExp(`^${label}`, "i") }).click();
  await settleResponsiveLayout(page);
}

async function choosePreviewMode(page, mode) {
  for (const menuClass of ["builder-compact-preview-menu", "builder-medium-preview-menu"]) {
    const trigger = page.locator(`.${menuClass} > button`);
    if (await trigger.isVisible().catch(() => false)) {
      await chooseCompactMenuItem(page, menuClass, mode);
      return;
    }
  }
  await page.locator('.builder-subbar .viewport-switcher button', { hasText: new RegExp(`^${mode}$`, "i") }).click();
  await settleResponsiveLayout(page);
}

async function inspectFluidResizeStep(page, issues, label, mode = "mobile") {
  const ratio = { tablet: 3 / 4, mobile: 390 / 844 }[mode] || null;
  const measurements = await page.evaluate(({ selectedMode, selectedRatio }) => {
    const root = document.documentElement;
    const workspace = document.querySelector(".builder-canvas-shell")?.getBoundingClientRect();
    const stage = document.querySelector(".builder-preview-stage")?.getBoundingClientRect();
    const device = document.querySelector(`.builder-device-frame.viewport-${selectedMode}`)?.getBoundingClientRect();
    return {
      rootFits: root.scrollWidth <= root.clientWidth + 1,
      workspace: workspace && { x: workspace.x, y: workspace.y, width: workspace.width, height: workspace.height },
      stage: stage && { x: stage.x, y: stage.y, width: stage.width, height: stage.height },
      device: device && { x: device.x, y: device.y, width: device.width, height: device.height },
      ratioFits: Boolean(
        device &&
        (!selectedRatio || Math.abs(device.width / device.height - selectedRatio) < 0.02)
      ),
    };
  }, { selectedMode: mode, selectedRatio: ratio });
  check(issues, measurements.rootFits, `${label}: global horizontal overflow appeared.`);
  check(issues, inside(measurements.device, measurements.workspace, 2), `${label}: preview left its workspace.`);
  check(issues, measurements.ratioFits, `${label}: preview aspect ratio changed.`);
  if (measurements.stage && measurements.device) {
    if (mode === "desktop") {
      check(
        issues,
        Math.abs(measurements.device.width - measurements.stage.width) <= 3 &&
          Math.abs(measurements.device.height - measurements.stage.height) <= 3,
        `${label}: desktop preview did not fill the available stage.`
      );
    } else {
      const maximumWidth = Math.min(measurements.stage.width, measurements.stage.height * ratio);
      check(
        issues,
        Math.abs(measurements.device.width - maximumWidth) <= 3,
        `${label}: preview did not maximize the available stage.`
      );
    }
  }
  return measurements.device;
}

async function inspectDevice(page, issues, label, mode = "mobile", { embedded = false } = {}) {
  const aspectRatios = {
    tablet: 3 / 4,
    mobile: 390 / 844,
  };
  const viewport = await page.evaluate(() => ({
    x: 0,
    y: 0,
    width: document.documentElement.clientWidth,
    height: window.innerHeight,
  }));
  const builder = await page.locator(".page-builder").boundingBox();
  const area = await page.locator(".builder-canvas-shell").boundingBox();
  const stage = await page.locator(".builder-preview-stage").boundingBox();
  const device = await page.locator(`.builder-device-frame.viewport-${mode}`).boundingBox();
  const compactPreviewControl = page.locator(".builder-compact-preview-menu > button");
  const mediumPreviewControl = page.locator(".builder-medium-preview-menu > button");
  let activeDeviceControl = null;
  if (await compactPreviewControl.isVisible().catch(() => false)) {
    activeDeviceControl = await compactPreviewControl.boundingBox();
  } else if (await mediumPreviewControl.isVisible().catch(() => false)) {
    activeDeviceControl = await mediumPreviewControl.boundingBox();
  } else {
    activeDeviceControl = await page.locator('.builder-subbar .viewport-switcher button[aria-pressed="true"]').boundingBox();
  }
  const inspector = await page.locator(".builder-inspector").boundingBox();
  if (!embedded) {
    check(issues, inside(builder, viewport, 2), `${label}: builder shell leaves the viewport.`);
  }
  check(issues, area && area.width >= 260 && area.height >= 260, `${label}: preview area is not usable.`);
  check(issues, stage && stage.width > 0 && stage.height > 0, `${label}: preview stage has zero dimensions.`);
  check(issues, device && device.width > 0 && device.height > 0, `${label}: preview has zero dimensions.`);
  check(issues, inside(device, area, 2), `${label}: preview leaves its workspace.`);
  check(issues, inside(stage, area, 2), `${label}: preview stage leaves its workspace.`);
  if (!embedded) {
    check(issues, inside(activeDeviceControl, viewport, 2), `${label}: active device control is clipped.`);
  }
  if (!embedded) {
    check(issues, !inspector || inside(inspector, viewport, 2), `${label}: inspector is clipped by the viewport.`);
  }
  check(issues, !inspector || !overlaps(inspector, area), `${label}: inspector overlaps the preview.`);
  if (device && mode !== "desktop") {
    check(
      issues,
      Math.abs(device.width / device.height - aspectRatios[mode]) < 0.02,
      `${label}: ${mode} aspect ratio changed.`
    );
  }
  if (device && stage) {
    if (mode === "desktop") {
      check(
        issues,
        Math.abs(device.width - stage.width) <= 3 && Math.abs(device.height - stage.height) <= 3,
        `${label}: desktop preview did not fill the available stage.`
      );
    } else {
      const maximumWidth = Math.min(stage.width, stage.height * aspectRatios[mode]);
      check(
        issues,
        Math.abs(device.width - maximumWidth) <= 3,
        `${label}: ${mode} preview did not maximize the available stage.`
      );
    }
  }
  return { area, stage, device, phone: mode === "mobile" ? device : null };
}

test("visual responsive acceptance: dashboard, drawer, builder, and phone", async ({ page }) => {
  test.setTimeout(8 * 60 * 1000);
  const issues = [];
  let auditStage = "public navigation";
  const setAuditStage = (stage) => {
    auditStage = stage;
    test.info().annotations.push({ type: "audit-stage", description: stage });
  };

  try {
    await page.setViewportSize({ width: 1024, height: 600 });
    await page.goto("/", { waitUntil: "domcontentloaded" });
    const hamburger = page.locator(".hamburger");
    await hamburger.waitFor({ state: "visible" });
    await hamburger.click();
    const menu = page.locator(".mobile-menu");
    const close = page.locator(".mobile-menu-close");
    await menu.waitFor({ state: "visible" });
    await page.waitForTimeout(250);
    const menuBox = await menu.boundingBox();
    const closeBox = await close.boundingBox();
    const viewportBox = { x: 0, y: 0, width: 1024, height: 600 };
    check(issues, inside(menuBox, viewportBox), "Public drawer is outside 1024x600.");
    check(issues, inside(closeBox, menuBox), "Public drawer close button is clipped.");
    check(issues, menuBox?.height <= 600, "Public drawer exceeds viewport height.");
    const bodyOverflow = await page.evaluate(() => getComputedStyle(document.body).overflow);
    check(issues, bodyOverflow === "hidden", "Background page still scrolls while the public drawer is open.");
    await capture(page, "public-menu-1024x600.png");
    await close.click();

    setAuditStage("login");
    await logIn(page);
    await page.setViewportSize({ width: 1024, height: 600 });
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
    await page.locator(".admin-dashboard-page").waitFor({ state: "visible" });
    const dashboardMain = await page.locator(".admin-dashboard-page").boundingBox();
    const dashboardSidebar = await page.locator(".admin-sidebar").boundingBox();
    check(issues, dashboardMain?.width >= 760, "Dashboard main content is too narrow at 1024x600.");
    check(
      issues,
      !overlaps(dashboardMain, dashboardSidebar),
      "Closed dashboard sidebar overlaps main content at 1024x600."
    );
    const visibleCards = page.locator(
      ".user-dashboard-main-grid > *, .user-dashboard-lower-grid > *, .overview-grid > *, .dashboard-panel"
    );
    const cardCount = await visibleCards.count();
    check(issues, cardCount > 0, "Dashboard rendered no visible content cards.");
    for (let index = 0; index < Math.min(cardCount, 8); index += 1) {
      const cardBox = await visibleCards.nth(index).boundingBox();
      if (cardBox && dashboardMain) {
        check(issues, inside(cardBox, dashboardMain, 2), "A dashboard card is cropped outside main content.");
      }
    }
    const dashboardTinyScrollers = await findTinyScrollRegions(page, ".admin-dashboard-layout");
    check(issues, dashboardTinyScrollers.length === 0, "Dashboard contains a tiny nested scrollbar.");
    await capture(page, "dashboard-1024x600.png");

    await page.setViewportSize({ width: 1366, height: 768 });
    await page.waitForTimeout(150);
    const wideMain = await page.locator(".admin-dashboard-page").boundingBox();
    const wideSidebar = await page.locator(".admin-sidebar").boundingBox();
    check(issues, !overlaps(wideMain, wideSidebar), "Desktop dashboard sidebar overlaps main content.");

    setAuditStage("builder navigation");
    await page.goto("/page-builder", { waitUntil: "domcontentloaded" });
    await page.locator(".builder-layout").waitFor({ state: "visible", timeout: 30_000 });
    const desktopBuilderSidebar = page.locator(".desktop-navigation-sidebar");
    check(issues, await desktopBuilderSidebar.isVisible(), "Large desktop global sidebar is hidden.");
    check(
      issues,
      (await desktopBuilderSidebar.boundingBox())?.width >= 68 &&
        (await desktopBuilderSidebar.boundingBox())?.width <= 265,
      "Large desktop sidebar width no longer matches its original route-specific size."
    );
    check(
      issues,
      !(await page.locator(".dashboard-mobile-menu-button").isVisible()),
      "Large desktop incorrectly shows the navigation hamburger."
    );
    await page.setViewportSize({ width: 1024, height: 600 });
    await settleResponsiveLayout(page);
    setAuditStage("builder loading");
    await page.locator(".builder-layout").waitFor({ state: "visible", timeout: 30_000 });
    setAuditStage("builder laptop assertions");
    const dashboardMenuButton = page.locator(".dashboard-mobile-menu-button");
    const dashboardDrawer = page.locator(".responsive-navigation-drawer");
    const persistentSidebar = page.locator(".desktop-navigation-sidebar");
    const closedRailBox = await persistentSidebar.boundingBox();
    const previewBeforeDrawer = await page.locator(".builder-canvas-shell").boundingBox();
    const closedBuilderPage = await page.locator(".page-builder-dashboard-page").boundingBox();
    check(issues, !closedRailBox, "Constrained builder still shows a persistent navigation rail.");
    check(issues, await dashboardMenuButton.isVisible(), "Constrained builder does not show the navigation hamburger.");
    check(
      issues,
      closedBuilderPage && closedBuilderPage.x <= 1 && closedBuilderPage.width >= 1023,
      "Collapsed navigation still reserves a sidebar grid column."
    );
    await capture(page, "page-builder-navigation-closed-1024x600.png");
    await dashboardMenuButton.click();
    await expect(page.locator(".admin-dashboard-layout")).toHaveClass(/sidebar-open/);
    await dashboardDrawer.waitFor({ state: "visible" });
    await expect(page.locator(".responsive-navigation-close")).toBeFocused();
    await page.keyboard.press("Shift+Tab");
    check(
      issues,
      await page.evaluate(() => document.querySelector(".responsive-navigation-drawer")?.contains(document.activeElement)),
      "Reverse tabbing escaped the open navigation drawer."
    );
    await page.keyboard.press("Tab");
    await expect(page.locator(".responsive-navigation-close")).toBeFocused();
    await page.locator(".responsive-navigation-content").evaluate((element) => {
      element.scrollTop = 0;
    });
    const openDrawerBox = await dashboardDrawer.boundingBox();
    const openCloseButtonBox = await page.locator(".responsive-navigation-close").boundingBox();
    const previewBehindDrawer = await page.locator(".builder-canvas-shell").boundingBox();
    check(issues, openDrawerBox?.width >= 320, "Open global navigation is narrower than 320px at 1024x600.");
    check(issues, openDrawerBox?.width <= 431, "Open global navigation is wider than its intended maximum.");
    check(
      issues,
      openDrawerBox && openDrawerBox.x >= -1 && openDrawerBox.x + openDrawerBox.width <= 1024 + 1,
      "Open builder navigation leaves the viewport."
    );
    check(issues, inside(openCloseButtonBox, openDrawerBox, 2), "Builder navigation close button is clipped.");
    await expect(page.locator(".dashboard-sidebar-backdrop")).toHaveCSS("opacity", "1");
    check(
      issues,
      Number.parseFloat(await page.locator(".dashboard-sidebar-backdrop").evaluate((element) => getComputedStyle(element).opacity)) > 0.5,
      "Builder navigation backdrop is not visible."
    );
    check(
      issues,
      previewBeforeDrawer && previewBehindDrawer &&
        Math.abs(previewBeforeDrawer.width - previewBehindDrawer.width) <= 2,
      "Opening the overlay drawer permanently shrinks the preview."
    );
    const drawerContentFits = await page.evaluate(() => {
      const drawer = document.querySelector(".responsive-navigation-drawer");
      if (!drawer) return false;
      const drawerRect = drawer.getBoundingClientRect();
      const important = [
        drawer.querySelector(".responsive-navigation-close"),
        ...drawer.querySelectorAll(".admin-sidebar-nav button"),
        ...drawer.querySelectorAll(".admin-sidebar-bottom button"),
      ].filter((element) => {
        if (!element) return false;
        const rect = element.getBoundingClientRect();
        return rect.bottom > drawerRect.top && rect.top < drawerRect.bottom;
      });
      return important.every((element) => {
        const rect = element.getBoundingClientRect();
        return rect.left >= drawerRect.left - 1 && rect.right <= drawerRect.right + 1;
      });
    });
    check(issues, drawerContentFits, "Important navigation content is clipped outside the open drawer.");
    const expandedDrawerContent = await page.evaluate(() => {
      const drawer = document.querySelector(".responsive-navigation-drawer");
      const sidebar = drawer?.querySelector(".responsive-navigation-content");
      const navigation = sidebar?.querySelector(".admin-sidebar-nav");
      const globalLabels = [...(sidebar?.querySelectorAll(".admin-sidebar-nav button > span") || [])];
      const firstNavItem = sidebar?.querySelector(".admin-sidebar-nav button");
      return {
        navigationDisplay: navigation ? getComputedStyle(navigation).display : "",
        navigationDirection: navigation ? getComputedStyle(navigation).flexDirection : "",
        sidebarWidth: sidebar?.getBoundingClientRect().width || 0,
        firstItemDisplay: firstNavItem ? getComputedStyle(firstNavItem).display : "",
        visibleGlobalLabels: globalLabels.filter((label) => label.getClientRects().length > 0).length,
      };
    });
    check(
      issues,
      expandedDrawerContent.navigationDisplay === "flex" &&
        expandedDrawerContent.navigationDirection === "column" &&
        expandedDrawerContent.sidebarWidth >= 320 &&
        expandedDrawerContent.firstItemDisplay === "flex" &&
        expandedDrawerContent.visibleGlobalLabels >= 5,
      "Open global navigation does not render a usable vertical icon-and-label list."
    );
    const drawerText = await dashboardDrawer.innerText();
    for (const builderOnlyLabel of [
      "Editing tools",
      "Current page",
      "New page",
      "Duplicate",
      "Templates",
      "Save changes",
      "Go Live",
      "Preview Site",
    ]) {
      check(
        issues,
        !drawerText.toLowerCase().includes(builderOnlyLabel.toLowerCase()),
        `${builderOnlyLabel} was incorrectly rendered inside global navigation.`
      );
    }
    check(
      issues,
      await page.locator(".builder-subbar").isVisible() && await page.locator(".builder-compact-controls").isVisible(),
      "Page Builder controls were not preserved in the builder behind the global drawer."
    );
    const nestedDrawerScrollerCount = await page.evaluate(() => {
      const drawer = document.querySelector(".responsive-navigation-drawer");
      if (!drawer) return 0;
      const allowed = new Set([
        drawer.querySelector(".responsive-navigation-scroll-content"),
      ]);
      return [...drawer.querySelectorAll("*")].filter((element) => {
        const style = getComputedStyle(element);
        return !allowed.has(element) && ["auto", "scroll"].includes(style.overflowY) && element.scrollHeight > element.clientHeight + 2;
      }).length;
    });
    check(issues, nestedDrawerScrollerCount === 0, "Open builder navigation creates nested vertical scrollbars.");
    await capture(page, "page-builder-navigation-drawer-1024x600.png");

    for (const [drawerWidth, drawerHeight] of [
      [1280, 720],
      [1146, 870],
      [1024, 768],
      [1024, 600],
      [768, 1024],
      [430, 932],
      [390, 844],
      [360, 800],
      [320, 568],
    ]) {
      if (await page.locator(".admin-dashboard-layout").evaluate((element) => element.classList.contains("sidebar-open"))) {
        await page.keyboard.press("Escape");
      }
      await page.setViewportSize({ width: drawerWidth, height: drawerHeight });
      await settleResponsiveLayout(page);
      check(issues, await dashboardMenuButton.isVisible(), `Navigation hamburger is hidden at ${drawerWidth}x${drawerHeight}.`);
      check(issues, !(await persistentSidebar.boundingBox()), `Closed global sidebar remains visible at ${drawerWidth}x${drawerHeight}.`);
      const releasedBuilderPage = await page.locator(".page-builder-dashboard-page").boundingBox();
      check(
        issues,
        releasedBuilderPage && releasedBuilderPage.x <= 1 && releasedBuilderPage.width >= drawerWidth - 1,
        `Closed global navigation reserves builder width at ${drawerWidth}x${drawerHeight}.`
      );
      if (!(drawerWidth === 1024 && drawerHeight === 600)) {
        await capture(page, `page-builder-navigation-closed-${drawerWidth}x${drawerHeight}.png`);
      }
      await dashboardMenuButton.click();
      await expect(page.locator(".admin-dashboard-layout")).toHaveClass(/sidebar-open/);
      const drawerBox = await dashboardDrawer.boundingBox();
      check(
        issues,
        drawerBox && drawerBox.width > 0 && drawerBox.x >= -1 && drawerBox.x + drawerBox.width <= drawerWidth + 1,
        `Navigation drawer leaves the viewport at ${drawerWidth}x${drawerHeight}.`
      );
      if (drawerWidth === 1024) {
        check(issues, drawerBox?.width >= 320 && drawerBox.width <= 431, `Navigation drawer width is unsuitable at 1024x${drawerHeight}.`);
      }
      const responsiveNavigationLayout = await dashboardDrawer.evaluate((drawer) => {
        const navigation = drawer.querySelector(".admin-sidebar-nav");
        const items = [...(navigation?.querySelectorAll("button, a") || [])];
        const labels = [...drawer.querySelectorAll(".admin-sidebar-nav button > span, .admin-sidebar-nav a > span")];
        const interactiveItems = [
          ...items,
          ...drawer.querySelectorAll(".admin-sidebar-bottom button"),
        ];
        const drawerRect = drawer.getBoundingClientRect();
        const account = drawer.querySelector(".admin-sidebar-user")?.getBoundingClientRect();
        const utilityGrid = drawer.querySelector(".admin-sidebar-bottom")?.getBoundingClientRect();
        const fullWidthSections = [
          drawer.querySelector(".admin-sidebar-brand"),
          drawer.querySelector(".admin-sidebar-search"),
          drawer.querySelector(".admin-sidebar-notifications"),
          navigation,
        ]
          .filter((element) => element?.getClientRects().length)
          .map((element) => element.getBoundingClientRect());
        return {
          navigationDisplay: navigation ? getComputedStyle(navigation).display : "",
          navigationDirection: navigation ? getComputedStyle(navigation).flexDirection : "",
          visibleLabelCount: labels.filter((label) => label.getClientRects().length > 0).length,
          startAlignedItems: items.every((item) => {
            const style = getComputedStyle(item);
            return style.justifyContent === "flex-start" && style.textAlign === "start";
          }),
          accessibleItems: interactiveItems.every((item) =>
            Boolean(item.getAttribute("aria-label")) && Boolean(item.getAttribute("title"))
          ),
          minimumTargets: interactiveItems.every((item) => {
            const rect = item.getBoundingClientRect();
            return rect.width >= 44 && rect.height >= 44;
          }),
          startAlignedGroups: items.every((item) => getComputedStyle(item).justifyContent === "flex-start"),
          equalNavigationRows: items.every((item) =>
            Math.abs(item.getBoundingClientRect().height - items[0].getBoundingClientRect().height) <= 1
          ),
          centeredAccount: Boolean(
            account &&
            utilityGrid &&
            Math.abs(account.left + account.width / 2 - (utilityGrid.left + utilityGrid.width / 2)) <= 1
          ),
          alignedFullWidthSections: fullWidthSections.every((rect) =>
            Math.abs(rect.left - fullWidthSections[0].left) <= 1 &&
            Math.abs(rect.right - fullWidthSections[0].right) <= 1
          ),
          drawerContentInside: fullWidthSections.every((rect) =>
            rect.left >= drawerRect.left - 1 && rect.right <= drawerRect.right + 1
          ),
          hasHorizontalOverflow: document.documentElement.scrollWidth > window.innerWidth + 1,
        };
      });
      check(
        issues,
        responsiveNavigationLayout.navigationDisplay === "flex" &&
          responsiveNavigationLayout.navigationDirection === "column",
        `Global navigation is not a vertical list at ${drawerWidth}x${drawerHeight}.`
      );
      check(
        issues,
        responsiveNavigationLayout.visibleLabelCount >= 5 &&
          responsiveNavigationLayout.startAlignedItems,
        `Global navigation labels are hidden or not start-aligned at ${drawerWidth}x${drawerHeight}.`
      );
      check(
        issues,
        responsiveNavigationLayout.startAlignedGroups &&
          responsiveNavigationLayout.equalNavigationRows &&
          responsiveNavigationLayout.centeredAccount,
        `Global navigation groups or account block are not aligned consistently at ${drawerWidth}x${drawerHeight}.`
      );
      check(
        issues,
        responsiveNavigationLayout.alignedFullWidthSections &&
          responsiveNavigationLayout.drawerContentInside,
        `Global navigation full-width sections do not share consistent padding at ${drawerWidth}x${drawerHeight}.`
      );
      check(
        issues,
        responsiveNavigationLayout.accessibleItems && responsiveNavigationLayout.minimumTargets,
        `Global navigation items lack accessible labels, tooltips, or touch targets at ${drawerWidth}x${drawerHeight}.`
      );
      check(
        issues,
        !responsiveNavigationLayout.hasHorizontalOverflow,
        `Global navigation creates horizontal overflow at ${drawerWidth}x${drawerHeight}.`
      );
      check(
        issues,
        await dashboardDrawer.locator(".admin-sidebar-search input").isVisible(),
        `Navigation search field is hidden at ${drawerWidth}x${drawerHeight}.`
      );
      const responsiveDrawerText = await dashboardDrawer.innerText();
      check(
        issues,
        !responsiveDrawerText.toLowerCase().includes("editing tools") &&
          !responsiveDrawerText.toLowerCase().includes("current page") &&
          !responsiveDrawerText.toLowerCase().includes("save changes"),
        `Builder-only controls entered global navigation at ${drawerWidth}x${drawerHeight}.`
      );
      if (!(drawerWidth === 1024 && drawerHeight === 600)) {
        await capture(page, `page-builder-navigation-open-${drawerWidth}x${drawerHeight}.png`);
      }
    }
    await page.setViewportSize({ width: 768, height: 1024 });
    await settleResponsiveLayout(page);
    check(
      issues,
      await dashboardDrawer.locator(".admin-sidebar-nav button > span").first().isVisible(),
      "Global navigation labels did not return after widening the open drawer."
    );
    await page.setViewportSize({ width: 390, height: 844 });
    await settleResponsiveLayout(page);
    check(
      issues,
      await dashboardDrawer.locator(".admin-sidebar-nav button > span").first().isVisible(),
      "Global navigation labels disappeared after narrowing the open drawer."
    );
    await page.setViewportSize({ width: 1024, height: 600 });
    await settleResponsiveLayout(page);
    await page.keyboard.press("Escape");
    await expect(page.locator(".admin-dashboard-layout")).not.toHaveClass(/sidebar-open/);
    await expect(dashboardMenuButton).toBeFocused();
    const previewAfterEscape = await page.locator(".builder-canvas-shell").boundingBox();
    check(
      issues,
      previewBeforeDrawer && previewAfterEscape &&
        Math.abs(previewBeforeDrawer.width - previewAfterEscape.width) <= 2,
      "Closing the drawer with Escape did not restore the preview interaction area."
    );
    check(
      issues,
      previewAfterEscape && previewBehindDrawer && openDrawerBox &&
        previewAfterEscape.width >
          Math.max(0, previewBehindDrawer.x + previewBehindDrawer.width - (openDrawerBox.x + openDrawerBox.width)) + 300,
      "Closing navigation did not restore the preview's unobstructed width."
    );
    await dashboardMenuButton.click();
    await expect(page.locator(".admin-dashboard-layout")).toHaveClass(/sidebar-open/);
    await page.locator(".dashboard-sidebar-backdrop").click({ position: { x: 900, y: 300 } });
    await expect(page.locator(".admin-dashboard-layout")).not.toHaveClass(/sidebar-open/);

    const compactControls = page.locator(".builder-compact-controls");
    check(issues, await compactControls.isVisible(), "Progressively disclosed builder controls are not visible at 1024x600.");
    const subbarFits = await page.locator(".builder-subbar").evaluate(
      (element) => element.scrollWidth <= element.clientWidth + 1
    );
    check(issues, subbarFits, "Builder toolbar requires horizontal scrolling at 1024x600.");
    const subbarBox = await page.locator(".builder-subbar").boundingBox();
    check(issues, subbarBox?.height <= 64, "Builder toolbar is too tall at 1024x600.");

    for (const menuClass of [
      "builder-compact-main-menu",
      "builder-compact-panel-menu",
      "builder-compact-preview-menu",
      "builder-compact-actions-menu",
    ]) {
      const trigger = page.locator(`.${menuClass} > button`);
      check(issues, await trigger.isVisible(), `${menuClass} trigger is not visible.`);
      check(issues, (await trigger.getAttribute("aria-expanded")) === "false", `${menuClass} lacks collapsed state.`);
      check(issues, Boolean(await trigger.getAttribute("aria-controls")), `${menuClass} lacks aria-controls.`);
      check(issues, Boolean(await trigger.getAttribute("title")), `${menuClass} lacks a tooltip.`);
    }

    const mainMenuResult = await openCompactMenu(page, "builder-compact-main-menu");
    const mainMenuBox = await mainMenuResult.menu.boundingBox();
    check(issues, inside(mainMenuBox, viewportBox, 2), "Main builder menu leaves the viewport.");
    await capture(page, "page-builder-1024x600-main-menu.png");
    for (const item of ["Pages", "Forms", "Reservations", "Header & Footer", "Users", "Publish"]) {
      check(
        issues,
        await mainMenuResult.menu.locator('[role^="menuitem"]', { hasText: new RegExp(`^${item}`, "i") }).count() === 1,
        `${item} is missing from the main builder menu.`
      );
    }
    await page.keyboard.press("Escape");
    check(issues, (await mainMenuResult.trigger.getAttribute("aria-expanded")) === "false", "Main menu did not close on Escape.");
    await mainMenuResult.trigger.focus();
    await page.keyboard.press("ArrowDown");
    check(issues, (await mainMenuResult.trigger.getAttribute("aria-expanded")) === "true", "Main menu did not open from the keyboard.");
    check(
      issues,
      await page.evaluate(() => document.activeElement?.getAttribute("role")?.startsWith("menuitem")),
      "Keyboard-opened main menu did not focus an item."
    );
    await page.keyboard.press("Escape");

    const actionsMenuResult = await openCompactMenu(page, "builder-compact-actions-menu");
    check(issues, inside(await actionsMenuResult.menu.boundingBox(), viewportBox, 2), "Actions menu leaves the viewport.");
    for (const item of ["Save changes", "Go Live"]) {
      check(
        issues,
        await actionsMenuResult.menu.locator('[role="menuitem"]', { hasText: new RegExp(`^${item}$`, "i") }).count() === 1,
        `${item} is not accessible from the actions menu.`
      );
    }
    await page.mouse.click(500, 300);
    check(issues, (await actionsMenuResult.trigger.getAttribute("aria-expanded")) === "false", "Actions menu did not close on outside click.");

    const previewMenuResult = await openCompactMenu(page, "builder-compact-preview-menu");
    check(issues, inside(await previewMenuResult.menu.boundingBox(), viewportBox, 2), "Preview mode menu leaves the viewport.");
    for (const item of ["Desktop", "Tablet", "Mobile", "Preview site"]) {
      check(
        issues,
        await previewMenuResult.menu.locator('[role^="menuitem"]', { hasText: new RegExp(`^${item}`, "i") }).count() === 1,
        `${item} is missing from the preview mode menu.`
      );
    }
    await page.keyboard.press("Escape");

    const visibleSidePanelCount = async () =>
      page.evaluate(() =>
        [document.querySelector(".builder-sidebar"), document.querySelector(".builder-inspector")]
          .filter((element) => element && getComputedStyle(element).display !== "none" && element.getBoundingClientRect().width > 0)
          .length
      );
    check(issues, (await visibleSidePanelCount()) === 0, "Constrained builder did not start in preview-first mode.");

    setAuditStage("builder selecting desktop");
    await choosePreviewMode(page, "desktop");
    setAuditStage("builder inspecting desktop");
    const initialDesktop = await inspectDevice(page, issues, "Desktop preview 1024x600", "desktop");
    const focusDesktopWidth = initialDesktop.device?.width || 0;
    await capture(page, "page-builder-1024x600-desktop.png");

    setAuditStage("builder opening tools");
    await chooseCompactMenuItem(page, "builder-compact-panel-menu", "Tools");
    setAuditStage("builder tools mode");
    const tools = await page.locator(".builder-sidebar").boundingBox();
    const toolsPreview = await page.locator(".builder-canvas-shell").boundingBox();
    const toolsStage = await page.locator(".builder-preview-stage").boundingBox();
    const builderLayout = await page.locator(".builder-layout").boundingBox();
    const toolsDesktop = await page.locator(".builder-device-frame.viewport-desktop").boundingBox();
    check(issues, tools && !overlaps(tools, toolsPreview), "Builder tools overlap the preview at 1024x600.");
    check(issues, tools && builderLayout && tools.width / builderLayout.width <= 0.3, "Tools panel consumes too much laptop width.");
    check(issues, toolsPreview && builderLayout && toolsPreview.width / builderLayout.width >= 0.68, "Tools mode does not leave most width for the preview.");
    check(issues, (await visibleSidePanelCount()) === 1, "Tools mode shows more than one side panel.");
    if (toolsStage && toolsDesktop) {
      check(
        issues,
        Math.abs(toolsDesktop.width - toolsStage.width) <= 3 &&
          Math.abs(toolsDesktop.height - toolsStage.height) <= 3,
        "Tools mode leaves usable preview-stage space empty at 1024x600."
      );
    }
    await capture(page, "page-builder-1024x600-tools-expanded.png");

    await chooseCompactMenuItem(page, "builder-compact-panel-menu", "Inspector");
    setAuditStage("builder inspector mode");
    const inspector = await page.locator(".builder-inspector").boundingBox();
    const inspectorPreview = await page.locator(".builder-canvas-shell").boundingBox();
    const inspectorDesktop = await page.locator(".builder-device-frame.viewport-desktop").boundingBox();
    check(issues, inspector && !overlaps(inspector, inspectorPreview), "Inspector overlaps the laptop preview.");
    check(issues, (await visibleSidePanelCount()) === 1, "Inspector mode shows more than one side panel.");
    await chooseCompactMenuItem(page, "builder-compact-panel-menu", "Preview");
    setAuditStage("builder focus mode");
    const focusedPreview = await page.locator(".builder-canvas-shell").boundingBox();
    const focusedDesktop = await page.locator(".builder-device-frame.viewport-desktop").boundingBox();
    check(
      issues,
      focusedPreview && inspectorPreview && focusedPreview.width > inspectorPreview.width + 100,
      "Closing the inspector did not enlarge the preview workspace."
    );
    check(
      issues,
      focusedDesktop && inspectorDesktop && focusedDesktop.width > inspectorDesktop.width + 100,
      "Closing the inspector did not enlarge the selected preview."
    );
    check(
      issues,
      focusedDesktop && Math.abs(focusedDesktop.width - focusDesktopWidth) < 2,
      "Preview did not return to its original focus size."
    );
    check(issues, toolsDesktop && toolsDesktop.width < focusDesktopWidth, "Opening tools did not reduce preview dimensions.");
    check(issues, focusedPreview && builderLayout && focusedPreview.width / builderLayout.width >= 0.9, "Collapsed panels do not give the preview most workspace width.");

    await choosePreviewMode(page, "tablet");
    setAuditStage("builder tablet mode");
    await inspectDevice(page, issues, "Tablet preview 1024x600", "tablet");
    await choosePreviewMode(page, "mobile");
    setAuditStage("builder mobile mode");
    await inspectDevice(page, issues, "Mobile preview 1024x600", "mobile");
    await capture(page, "page-builder-1024x600.png");

    setAuditStage("continuous width resizing");
    const navigationCount = await page.evaluate(
      () => performance.getEntriesByType("navigation").length
    );
    setAuditStage("desktop and laptop arrangement transitions");
    let desktopSidebarFontSize = 0;
    let laptopSidebarFontSize = 0;
    for (const sample of [
      { width: 1920, height: 1080, controls: "wide", panels: 2 },
      { width: 1600, height: 900, controls: "wide", panels: 2 },
      { width: 1536, height: 864, controls: "wide", panels: 2 },
      { width: 1366, height: 768, controls: "medium", panels: 1 },
      { width: 1280, height: 800, controls: "medium", panels: 1 },
      { width: 1280, height: 720, controls: "medium", panels: 1 },
      { width: 1024, height: 768, controls: "compact", panels: 0 },
      { width: 1024, height: 600, controls: "compact", panels: 0 },
    ]) {
      await page.setViewportSize({ width: sample.width, height: sample.height });
      await settleResponsiveLayout(page);
      await choosePreviewMode(page, "desktop");
      const controlVisibility = await page.evaluate(() => ({
        wide: getComputedStyle(document.querySelector(".builder-wide-controls")).display !== "none",
        medium: getComputedStyle(document.querySelector(".builder-medium-controls")).display !== "none",
        compact: getComputedStyle(document.querySelector(".builder-compact-controls")).display !== "none",
      }));
      check(issues, controlVisibility[sample.controls], `${sample.width}x${sample.height} did not use ${sample.controls} controls.`);
      check(
        issues,
        Object.entries(controlVisibility).filter(([, visible]) => visible).length === 1,
        `${sample.width}x${sample.height} shows multiple toolbar arrangements.`
      );
      check(
        issues,
        (await visibleSidePanelCount()) === sample.panels,
        `${sample.width}x${sample.height} shows the wrong number of side panels.`
      );
      const arrangement = await inspectDevice(page, issues, `Arrangement ${sample.width}x${sample.height}`, "desktop");
      const arrangementLayout = await page.locator(".builder-layout").boundingBox();
      const arrangementTools = await page.locator(".builder-sidebar").boundingBox();
      const arrangementInspector = await page.locator(".builder-inspector").boundingBox();
      check(
        issues,
        arrangement.area && arrangementLayout &&
          Math.abs(arrangement.area.y + arrangement.area.height - (arrangementLayout.y + arrangementLayout.height)) <= 2,
        `${sample.width}x${sample.height} preview region stops above the builder body bottom.`
      );
      check(
        issues,
        arrangement.device && arrangement.stage &&
          Math.abs(arrangement.device.y + arrangement.device.height - (arrangement.stage.y + arrangement.stage.height)) <= 3,
        `${sample.width}x${sample.height} desktop canvas leaves unused space below it.`
      );
      if (arrangementTools) {
        check(
          issues,
          arrangement.area && Math.abs(arrangement.area.x - (arrangementTools.x + arrangementTools.width)) <= 2,
          `${sample.width}x${sample.height} preview does not begin at the tools-panel edge.`
        );
        check(
          issues,
          arrangementLayout &&
            Math.abs(arrangementTools.y + arrangementTools.height - (arrangementLayout.y + arrangementLayout.height)) <= 2,
          `${sample.width}x${sample.height} tools panel does not fill the builder row.`
        );
      }
      if (arrangementInspector) {
        check(
          issues,
          arrangement.area && Math.abs(arrangement.area.x + arrangement.area.width - arrangementInspector.x) <= 2,
          `${sample.width}x${sample.height} preview does not end at the inspector edge.`
        );
        check(
          issues,
          arrangementLayout &&
            Math.abs(arrangementInspector.y + arrangementInspector.height - (arrangementLayout.y + arrangementLayout.height)) <= 2,
          `${sample.width}x${sample.height} inspector does not fill the builder row.`
        );
      }
      if (sample.controls === "medium") {
        check(
          issues,
          arrangement.area && arrangementLayout && arrangement.area.width / arrangementLayout.width >= 0.75,
          `${sample.width}x${sample.height} leaves a hidden panel track beside the preview.`
        );
      }
      await capture(page, `page-builder-layout-${sample.width}x${sample.height}.png`);
      const sidebarFontSize = await page.locator(".builder-sidebar").evaluate(
        (element) => Number.parseFloat(getComputedStyle(element).fontSize)
      );
      if (sample.width === 1536) desktopSidebarFontSize = sidebarFontSize;
      if (sample.width === 1280 && sample.height === 720) laptopSidebarFontSize = sidebarFontSize;
    }
    check(
      issues,
      laptopSidebarFontSize >= 12 && laptopSidebarFontSize <= desktopSidebarFontSize,
      "Laptop typography is either unreadably small or larger than desktop typography."
    );

    for (const [width, height, expectedControls, expectedPanels] of [
      [1536, 864, "wide", 2],
      [1024, 600, "compact", 0],
      [800, 700, "compact", 0],
      [1024, 600, "compact", 0],
      [1536, 864, "wide", 2],
    ]) {
      await page.setViewportSize({ width, height });
      await settleResponsiveLayout(page);
      const visibleControls = await page.evaluate(() => ({
        wide: getComputedStyle(document.querySelector(".builder-wide-controls")).display !== "none",
        medium: getComputedStyle(document.querySelector(".builder-medium-controls")).display !== "none",
        compact: getComputedStyle(document.querySelector(".builder-compact-controls")).display !== "none",
      }));
      check(issues, visibleControls[expectedControls], `${width}x${height} retained a stale toolbar arrangement.`);
      check(issues, (await visibleSidePanelCount()) === expectedPanels, `${width}x${height} retained stale panel state.`);
    }

    await page.setViewportSize({ width: 1024, height: 900 });
    await settleResponsiveLayout(page);
    const tallDesktop = await page.locator(".builder-device-frame.viewport-desktop").boundingBox();
    await page.setViewportSize({ width: 1024, height: 600 });
    await settleResponsiveLayout(page);
    const shortDesktop = await page.locator(".builder-device-frame.viewport-desktop").boundingBox();
    await page.setViewportSize({ width: 1024, height: 900 });
    await settleResponsiveLayout(page);
    const restoredDesktop = await page.locator(".builder-device-frame.viewport-desktop").boundingBox();
    check(issues, tallDesktop && shortDesktop && tallDesktop.height > shortDesktop.height + 5, "Short-height density did not resize the preview.");
    check(
      issues,
      tallDesktop && restoredDesktop &&
        Math.abs(tallDesktop.width - restoredDesktop.width) < 2 &&
        Math.abs(tallDesktop.height - restoredDesktop.height) < 2,
      "Preview dimensions remained stale after height expansion."
    );

    await choosePreviewMode(page, "mobile");
    const descendingWidths = [];
    for (let width = 1920; width >= 320; width -= 64) descendingWidths.push(width);
    if (descendingWidths.at(-1) !== 320) descendingWidths.push(320);
    const ascendingWidths = [...descendingWidths].reverse();
    let widestWidthDevice = null;
    let narrowestWidthDevice = null;
    for (const [direction, widths] of [
      ["contracting", descendingWidths],
      ["expanding", ascendingWidths],
    ]) {
      for (const width of widths) {
        await page.setViewportSize({ width, height: 800 });
        await settleResponsiveLayout(page);
        const device = await inspectFluidResizeStep(page, issues, `Width ${direction} ${width}x800`);
        if (width === 1920) widestWidthDevice = device;
        if (width === 320) narrowestWidthDevice = device;
      }
    }
    check(
      issues,
      widestWidthDevice && narrowestWidthDevice && widestWidthDevice.width > narrowestWidthDevice.width + 5,
      "Preview did not shrink and grow during the bidirectional width sweep."
    );

    setAuditStage("continuous height resizing");
    const descendingHeights = [];
    for (let height = 1080; height >= 500; height -= 40) descendingHeights.push(height);
    if (descendingHeights.at(-1) !== 500) descendingHeights.push(500);
    const ascendingHeights = [...descendingHeights].reverse();
    let tallestHeightDevice = null;
    let shortestHeightDevice = null;
    for (const [direction, heights] of [
      ["contracting", descendingHeights],
      ["expanding", ascendingHeights],
    ]) {
      for (const height of heights) {
        await page.setViewportSize({ width: 1024, height });
        await settleResponsiveLayout(page);
        const device = await inspectFluidResizeStep(page, issues, `Height ${direction} 1024x${height}`);
        if (height === 1080) tallestHeightDevice = device;
        if (height === 500) shortestHeightDevice = device;
      }
    }
    check(
      issues,
      tallestHeightDevice && shortestHeightDevice && tallestHeightDevice.width > shortestHeightDevice.width + 50,
      "Preview did not shrink and grow during the bidirectional height sweep."
    );
    check(
      issues,
      (await page.evaluate(() => performance.getEntriesByType("navigation").length)) === navigationCount,
      "The builder refreshed during responsive transitions."
    );

    setAuditStage("required builder screenshots");
    for (const [width, height] of [
      [1920, 1080],
      [1600, 900],
      [1536, 864],
      [1366, 768],
      [1280, 720],
      [1280, 800],
      [1024, 768],
      [1024, 600],
      [768, 1024],
      [430, 932],
      [390, 844],
      [360, 800],
    ]) {
      await page.setViewportSize({ width, height });
      await settleResponsiveLayout(page);
      await inspectDevice(page, issues, `Required screenshot ${width}x${height}`);
      await capture(page, `page-builder-${width}x${height}.png`);
    }

    setAuditStage("builder workspace switching");
    await chooseCompactMenuItem(page, "builder-compact-main-menu", "Forms");
    await chooseCompactMenuItem(page, "builder-compact-main-menu", "Pages");
    await page.locator(".builder-device-frame.viewport-mobile").waitFor({ state: "visible" });
    await settleResponsiveLayout(page);
    await inspectDevice(page, issues, "Preview after workspace tab switch");

    setAuditStage("image resizing");
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto("/demo", { waitUntil: "domcontentloaded" });
    await page.locator(".builder-layout").waitFor({ state: "visible", timeout: 30_000 });
    const modalBackdrop = page.locator(".builder-modal-backdrop");
    if (await modalBackdrop.isVisible().catch(() => false)) {
      await modalBackdrop.click({ position: { x: 4, y: 4 } }).catch(() => {});
    }
    await choosePreviewMode(page, "mobile");
    const imageFrame = page.locator(".direct-element-frame-image").first();
    if ((await imageFrame.count()) === 0) {
      issues.push("Demo project has no image frame for the image-resize acceptance check.");
    } else {
      await imageFrame.click({ position: { x: 12, y: 12 } });
      await page.waitForTimeout(100);
      const handle = page.locator(".direct-element-frame-image .direct-resize-handle").first();
      await handle.scrollIntoViewIfNeeded();
      const before = await imageFrame.boundingBox();
      const beforeStyle = await imageFrame.getAttribute("style");
      const handleBefore = await handle.boundingBox();
      if (handleBefore) {
        const handleHitTarget = await page.evaluate(({ x, y }) => {
          const target = document.elementFromPoint(x, y);
          return target?.closest?.(".direct-resize-handle") ? "resize-handle" : String(target?.className || target?.tagName || "none").slice(0, 80);
        }, {
          x: handleBefore.x + handleBefore.width / 2,
          y: handleBefore.y + handleBefore.height / 2,
        });
        check(issues, handleHitTarget === "resize-handle", `Image resize handle is not hit-testable (${handleHitTarget}).`);
        await page.mouse.move(handleBefore.x + handleBefore.width / 2, handleBefore.y + handleBefore.height / 2);
        await page.mouse.down();
        await page.waitForTimeout(100);
        const activeInteraction = await page.locator(".page-builder").getAttribute("data-builder-interaction");
        check(issues, activeInteraction === "resize", "Image resize handle did not initiate a resize interaction.");
        // Shrink the demo image: the starter image already occupies the mobile
        // canvas width, so growing it would correctly clamp at the boundary.
        await page.mouse.move(handleBefore.x - 34, handleBefore.y - 22, { steps: 5 });
        await page.mouse.up();
        await page.waitForTimeout(100);
      }
      const after = await imageFrame.boundingBox();
      const afterStyle = await imageFrame.getAttribute("style");
      const handleAfter = await handle.boundingBox();
      check(
        issues,
        before && after && (after.width !== before.width || after.height !== before.height),
        `Image resize did not update immediately (style changed: ${beforeStyle !== afterStyle}).`
      );
      check(
        issues,
        before && after && Math.abs(before.width / before.height - after.width / after.height) < 0.03,
        "Image resizing changed the image frame aspect ratio."
      );
      check(
        issues,
        after && handleAfter && Math.abs(handleAfter.x + handleAfter.width / 2 - (after.x + after.width)) < 14,
        "Image resize handle detached from the selected image."
      );
      const objectFit = await imageFrame.locator("img").evaluate((image) => getComputedStyle(image).objectFit);
      check(issues, objectFit === "contain", "Builder image does not preserve its aspect ratio with object-fit: contain.");
      await inspectDevice(page, issues, "Phone after image resize", "mobile", { embedded: true });
      await capture(page, "phone-preview-image-resize.png");
    }
  } catch (error) {
    const safeLoginFailure = String(error?.message || "").match(
      /Dedicated test-account login failed \(\d+\)\./,
    )?.[0];
    issues.push(
      `The visual responsive audit encountered an unexpected browser failure during ${auditStage}.${
        safeLoginFailure ? ` ${safeLoginFailure}` : ""
      }`,
    );
  } finally {
    await neutralizeSession(page, issues);
  }

  expect(issues, "Visual responsive acceptance failures.").toEqual([]);
});
