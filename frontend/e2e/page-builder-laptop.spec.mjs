import { expect, test } from "@playwright/test";

const viewports = [
  [1920, 1080],
  [1536, 864],
  [1440, 900],
  [1428, 726],
  [1366, 768],
  [1280, 720],
  [1146, 870],
  [1024, 768],
  [1024, 600],
  [900, 600],
  [768, 1024],
  [430, 932],
  [390, 844],
  [360, 800],
];

const originalWorkspaceLabels = [
  "Pages",
  "Forms",
  "Reservations",
  "Header & Footer",
  "Users",
  "Publish",
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

async function openBuilder(page) {
  await page.goto("/page-builder", { waitUntil: "domcontentloaded" });
  await page.locator(".page-builder").waitFor({ state: "visible", timeout: 30_000 });
  await page.evaluate(
    () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  );
}

test("original Page Builder chrome and proportional grid remain stable", async ({ page }) => {
  await logIn(page);

  for (const [width, height] of viewports) {
    await page.setViewportSize({ width, height });
    await openBuilder(page);

    const result = await page.evaluate(() => {
      const root = document.documentElement;
      const shell = document.querySelector(".admin-dashboard-layout");
      const builder = document.querySelector(".page-builder");
      const layout = builder?.querySelector(".builder-layout");
      const sidebar = builder?.querySelector(".builder-sidebar");
      const preview = builder?.querySelector(".builder-canvas-shell");
      const inspector = builder?.querySelector(".builder-inspector");
      const title = builder?.querySelector(".builder-brand h1")?.getBoundingClientRect();
      const hamburger = document.querySelector(".dashboard-mobile-menu-button");
      const hamburgerStyle = hamburger ? getComputedStyle(hamburger) : null;
      const hamburgerRect = hamburgerStyle?.display !== "none" ? hamburger.getBoundingClientRect() : null;
      const boxes = [layout, sidebar, preview, inspector].map((element) =>
        element && getComputedStyle(element).display !== "none" ? element.getBoundingClientRect() : null
      );
      const [layoutBox, sidebarBox, previewBox, inspectorBox] = boxes;
      const overlaps = Boolean(
        title && hamburgerRect &&
        title.left < hamburgerRect.right && title.right > hamburgerRect.left &&
        title.top < hamburgerRect.bottom && title.bottom > hamburgerRect.top
      );
      const shellStyle = shell ? getComputedStyle(shell) : null;

      return {
        documentFits: root.scrollWidth <= root.clientWidth + 1,
        layoutScale: Number(shellStyle?.getPropertyValue("--ui-layout-scale") || 0),
        textScale: Number(shellStyle?.getPropertyValue("--ui-text-scale") || 0),
        mobileBlocked: getComputedStyle(builder.querySelector(".builder-mobile-blocker")).display !== "none",
        titleOverlapsHamburger: overlaps,
        layout: layoutBox && { x: layoutBox.x, y: layoutBox.y, width: layoutBox.width, height: layoutBox.height },
        sidebar: sidebarBox && { x: sidebarBox.x, y: sidebarBox.y, width: sidebarBox.width, height: sidebarBox.height },
        preview: previewBox && { x: previewBox.x, y: previewBox.y, width: previewBox.width, height: previewBox.height },
        inspector: inspectorBox && { x: inspectorBox.x, y: inspectorBox.y, width: inspectorBox.width, height: inspectorBox.height },
      };
    });

    const expectedLayoutScale = Math.max(0.67, Math.min(1, width / 1440, height / 900));
    const expectedTextScale = Math.max(0.82, expectedLayoutScale);
    expect(result.layoutScale, `${width}x${height} layout scale`).toBeCloseTo(expectedLayoutScale, 3);
    expect(result.textScale, `${width}x${height} text scale`).toBeCloseTo(expectedTextScale, 3);
    expect(result.documentFits, `${width}x${height}`).toBeTruthy();
    expect(result.titleOverlapsHamburger, `${width}x${height}`).toBeFalsy();

    if (width < 900) {
      expect(result.mobileBlocked, `${width}x${height}`).toBeTruthy();
      continue;
    }

    expect(result.mobileBlocked, `${width}x${height}`).toBeFalsy();
    for (const box of [result.layout, result.sidebar, result.preview, result.inspector]) {
      expect(box, `${width}x${height} missing builder region`).toBeTruthy();
    }
    expect(Math.abs(result.sidebar.y - result.preview.y), `${width}x${height}`).toBeLessThanOrEqual(1);
    expect(Math.abs(result.inspector.y - result.preview.y), `${width}x${height}`).toBeLessThanOrEqual(1);
    expect(Math.abs(result.sidebar.height - result.preview.height), `${width}x${height}`).toBeLessThanOrEqual(1);
    expect(Math.abs(result.inspector.height - result.preview.height), `${width}x${height}`).toBeLessThanOrEqual(1);
    expect(result.sidebar.x + result.sidebar.width).toBeCloseTo(result.preview.x, 0);
    expect(result.preview.x + result.preview.width).toBeCloseTo(result.inspector.x, 0);
    expect(result.inspector.x + result.inspector.width).toBeCloseTo(result.layout.x + result.layout.width, 0);
    expect(result.sidebar.width).toBeGreaterThanOrEqual(149);
    expect(result.sidebar.width).toBeLessThanOrEqual(321);
    expect(result.inspector.width).toBeGreaterThanOrEqual(169);
    expect(result.inspector.width).toBeLessThanOrEqual(401);
    expect(result.preview.width / result.layout.width).toBeGreaterThan(0.35);

    const toolbar = page.locator(".builder-subbar");
    await expect(toolbar.locator('.builder-responsive-toolbar, select[aria-label="Panel"], select[aria-label="Device"]')).toHaveCount(0);
    await expect(toolbar.getByText("Hide panel", { exact: true })).toHaveCount(0);
    await expect(toolbar.getByText("Actions", { exact: true })).toHaveCount(0);
    for (const label of originalWorkspaceLabels) {
      await expect(toolbar.getByRole("button", { name: label, exact: true })).toHaveCount(1);
    }
  }
});

test("1024x600 keeps original panels functional and drag-and-drop reaches the preview", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 600 });
  await logIn(page);
  await openBuilder(page);

  const builder = page.locator(".page-builder");
  const sidebar = page.locator(".builder-sidebar");
  const inspector = page.locator(".builder-inspector");
  await expect(sidebar).toBeVisible();
  await expect(inspector).toBeVisible();
  await expect(sidebar.getByRole("button", { name: "Save changes", exact: true })).toBeVisible();
  await expect(sidebar.getByRole("button", { name: "Go Live", exact: true })).toBeVisible();

  await sidebar.locator(".panel-navigator button", { hasText: "Sections" }).click();
  const countBefore = await page.locator(".direct-element-frame").count();
  const dropReachedPreview = await page.evaluate(async () => {
    const source = document.querySelector('.section-component-palette button[draggable="true"]');
    const target = document.querySelector(".direct-layout-frame");
    if (!source || !target) return false;
    source.scrollIntoView({ block: "center" });
    const transfer = new DataTransfer();
    source.dispatchEvent(new DragEvent("dragstart", { bubbles: true, cancelable: true, dataTransfer: transfer }));
    await new Promise((resolve) => requestAnimationFrame(resolve));
    const rect = target.getBoundingClientRect();
    const clientX = rect.left + Math.max(20, Math.min(rect.width - 20, rect.width / 2));
    const clientY = rect.top + Math.max(20, Math.min(rect.height - 20, 100));
    const hitTarget = document.elementFromPoint(clientX, clientY)?.closest(".direct-layout-frame");
    target.dispatchEvent(new DragEvent("dragover", { bubbles: true, cancelable: true, clientX, clientY, dataTransfer: transfer }));
    target.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, clientX, clientY, dataTransfer: transfer }));
    source.dispatchEvent(new DragEvent("dragend", { bubbles: true, dataTransfer: transfer }));
    return hitTarget === target;
  });

  expect(dropReachedPreview).toBeTruthy();
  await expect(page.locator(".direct-element-frame")).toHaveCount(countBefore + 1);
  await expect(page.locator(".direct-element-frame.is-selected")).toHaveCount(1);
  await expect(builder.locator(".builder-inspector")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBeTruthy();
});
