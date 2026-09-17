import { expect, test } from "@playwright/test";

const widths = [360, 390, 480, 600, 601, 768, 1024, 1025, 1200, 1440, 1920];

const profiles = {
  360: ["mobile", 390, 360 / 390],
  390: ["mobile", 390, 1],
  480: ["mobile", 390, 1],
  600: ["mobile", 390, 1],
  601: ["tablet", 768, 601 / 768],
  768: ["tablet", 768, 1],
  1024: ["tablet", 768, 1],
  1025: ["desktop", 1200, 1025 / 1200],
  1200: ["desktop", 1200, 1],
  1440: ["desktop", 1200, 1],
  1920: ["desktop", 1200, 1],
};

const positions = {
  desktop: { x: 100, y: 80, width: 320, height: 90 },
  tablet: { x: 40, y: 50, width: 280, height: 80 },
  mobile: { x: 20, y: 30, width: 200, height: 70 },
};

const publishedSchema = {
  theme: {},
  siteChrome: { showHeader: false, showFooter: false },
  pages: [{
    id: "page_1",
    name: "Home",
    slug: "/",
    isDefault: true,
    visibility: "public",
    sections: [{
      id: "section_1",
      mode: "direct",
      layout: { width: "full", background: "rgb(12, 34, 56)", minHeight: 500 },
      freeElements: [{
        id: "element_1",
        type: "text",
        name: "Parity text",
        content: "Stable artboard geometry",
        styles: { color: "rgb(255, 255, 255)", fontSize: "24px", lineHeight: "1.4" },
        position: positions,
      }],
    }],
  }],
};

test("published layout uses saved artboards, full bleed, and controlled snapshots", async ({ page }) => {
  await page.route("**/api/public/sites/artboard-test**", async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith("/auth/status")) {
      await route.fulfill({ json: { success: true, user: null } });
      return;
    }
    await route.fulfill({
      json: {
        success: true,
        site: { subdomain: "artboard-test", brand: "Artboard Test" },
        project: {
          published_schema: publishedSchema,
          published_version: 1,
          published_revision: 1,
        },
      },
    });
  });

  await page.setViewportSize({ width: 1200, height: 900 });
  await page.goto("/site/artboard-test/", { waitUntil: "networkidle" });
  for (const width of widths) {
    await page.setViewportSize({ width, height: 900 });
    const [mode, logicalWidth, zoom] = profiles[width];
    const camera = page.locator(".site-renderer-camera");
    const artboard = page.locator(".site-renderer-artboard");
    const section = page.locator(".site-section");
    const bleed = page.locator(".site-section-bleed-background");
    const element = page.locator("[data-builder-element-id='element_1']");
    await expect(camera).toHaveAttribute("data-viewport-mode", mode);
    await expect(camera).toHaveAttribute("data-logical-width", String(logicalWidth));
    await expect.poll(async () => Number(await camera.getAttribute("data-presentation-zoom")))
      .toBeCloseTo(zoom, 4);
    await expect.poll(async () => (await bleed.boundingBox())?.width || 0)
      .toBeCloseTo(width, 1);

    const geometry = await page.evaluate(() => {
      const describe = (selector) => {
        const node = document.querySelector(selector);
        const rect = node.getBoundingClientRect();
        return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
      };
      const cameraNode = document.querySelector(".site-renderer-camera");
      const artboardRect = describe(".site-renderer-artboard");
      const elementRect = describe("[data-builder-element-id='element_1']");
      return {
        zoom: Number(cameraNode.dataset.presentationZoom),
        artboard: artboardRect,
        section: describe(".site-section"),
        bleed: describe(".site-section-bleed-background"),
        physicalLogicalRect: {
          x: elementRect.x - artboardRect.x,
          y: elementRect.y - artboardRect.y,
          width: elementRect.width,
          height: elementRect.height,
        },
        resolvedLogicalRect: {
          x: Number(document.querySelector("[data-builder-element-id='element_1']").dataset.logicalX),
          y: Number(document.querySelector("[data-builder-element-id='element_1']").dataset.logicalY),
          width: Number(document.querySelector("[data-builder-element-id='element_1']").dataset.logicalWidth),
          height: Number(document.querySelector("[data-builder-element-id='element_1']").dataset.logicalHeight),
        },
      };
    });

    expect(geometry.zoom).toBeCloseTo(zoom, 4);
    expect(geometry.artboard.width / geometry.zoom).toBeCloseTo(logicalWidth, 1);
    expect(geometry.artboard.x).toBeCloseTo((width - geometry.artboard.width) / 2, 1);
    expect(geometry.section.width).toBeCloseTo(geometry.artboard.width, 1);
    expect(geometry.bleed.width).toBeCloseTo(width, 1);
    for (const key of ["x", "y", "width", "height"]) {
      expect(geometry.physicalLogicalRect[key] / geometry.zoom).toBeCloseTo(geometry.resolvedLogicalRect[key], 1);
    }
    if ([390, 768, 1200].includes(width)) {
      expect(await artboard.screenshot({ animations: "disabled" }))
        .toMatchSnapshot(`legacy-artboard-${width}.png`);
    }
  }

});

test("editor viewport scrolls an exact camera stage and does not clip boundary overlays", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.setContent(`
    <link rel="stylesheet" href="/src/styles/index.css">
    <div class="page-builder">
      <main class="builder-canvas-shell editor-viewport camera-manual" style="width:500px;height:420px;box-sizing:border-box">
        <div class="editor-camera-stage" style="width:1200px">
          <div class="site-renderer-camera" style="width:1200px;height:300px">
            <div class="builder-canvas site-renderer-artboard" style="position:relative;width:1200px;height:300px;min-height:0;border:0;border-radius:0">
              <section class="site-section direct-layout-section" style="position:relative;width:1200px;height:300px">
                <div class="direct-layout-frame" style="width:1200px;height:300px">
                  <div id="top-left" class="direct-element-frame is-selected" style="position:absolute;left:0;top:0;width:100px;height:80px">
                    <div class="editor-overlay editor-element-overlay">
                      <button class="direct-move-handle" aria-label="Move boundary element"></button>
                    </div>
                  </div>
                  <div id="bottom-right" class="direct-element-frame is-selected" style="position:absolute;left:1100px;top:220px;width:100px;height:80px">
                    <div class="editor-overlay editor-element-overlay">
                      <button class="direct-resize-handle" aria-label="Resize boundary element"></button>
                    </div>
                  </div>
                </div>
              </section>
            </div>
          </div>
        </div>
      </main>
    </div>
  `);
  await page.waitForLoadState("networkidle");

  const viewport = page.locator(".editor-viewport");
  const stage = page.locator(".editor-camera-stage");
  const artboard = page.locator(".site-renderer-artboard");
  await expect(stage).toHaveCSS("width", "1200px");
  await expect(artboard).toHaveCSS("width", "1200px");

  const initial = await page.evaluate(() => {
    const viewportNode = document.querySelector(".editor-viewport");
    const artboardRect = document.querySelector(".site-renderer-artboard").getBoundingClientRect();
    const move = document.querySelector(".direct-move-handle");
    const moveRect = move.getBoundingClientRect();
    const moveCenter = [moveRect.left + moveRect.width / 2, moveRect.top + moveRect.height / 2];
    return {
      clientWidth: viewportNode.clientWidth,
      scrollWidth: viewportNode.scrollWidth,
      artboardWidth: artboardRect.width,
      moveEscapesLeft: moveRect.left < artboardRect.left,
      moveEscapesTop: moveRect.top < artboardRect.top,
      moveIsHit: document.elementsFromPoint(...moveCenter).includes(move),
    };
  });
  expect(initial.scrollWidth).toBeGreaterThan(initial.clientWidth);
  expect(initial.artboardWidth).toBeCloseTo(1200, 1);
  expect(initial.moveEscapesLeft).toBe(true);
  expect(initial.moveEscapesTop).toBe(true);
  expect(initial.moveIsHit).toBe(true);

  await viewport.evaluate((node) => { node.scrollLeft = node.scrollWidth; });
  const trailing = await page.evaluate(() => {
    const artboardRect = document.querySelector(".site-renderer-artboard").getBoundingClientRect();
    const resize = document.querySelector(".direct-resize-handle");
    const resizeRect = resize.getBoundingClientRect();
    const center = [resizeRect.left + resizeRect.width / 2, resizeRect.top + resizeRect.height / 2];
    return {
      escapesRight: resizeRect.right > artboardRect.right,
      escapesBottom: resizeRect.bottom > artboardRect.bottom,
      isHit: document.elementsFromPoint(...center).includes(resize),
    };
  });
  expect(trailing.escapesRight).toBe(true);
  expect(trailing.escapesBottom).toBe(true);
  expect(trailing.isHit).toBe(true);

  const cameraCases = [
    { workspaceWidth: 1600, zoom: 0.9 },
    { workspaceWidth: 700, zoom: 0.9 },
    { workspaceWidth: 1600, zoom: 1 },
    { workspaceWidth: 700, zoom: 1 },
    { workspaceWidth: 1600, zoom: 1.25 },
    { workspaceWidth: 700, zoom: 1.25 },
  ];
  for (const { workspaceWidth, zoom } of cameraCases) {
    const expectedWidth = 1200 * zoom;
    const geometry = await page.evaluate(({ workspaceWidth, expectedWidth }) => {
      const viewportNode = document.querySelector(".editor-viewport");
      const stageNode = document.querySelector(".editor-camera-stage");
      const cameraNode = document.querySelector(".site-renderer-camera");
      const artboardNode = document.querySelector(".site-renderer-artboard");
      viewportNode.style.width = workspaceWidth + "px";
      stageNode.style.width = expectedWidth + "px";
      cameraNode.style.width = expectedWidth + "px";
      artboardNode.style.width = expectedWidth + "px";
      return {
        stageWidth: stageNode.getBoundingClientRect().width,
        artboardWidth: artboardNode.getBoundingClientRect().width,
        clientWidth: viewportNode.clientWidth,
        scrollWidth: viewportNode.scrollWidth,
      };
    }, { workspaceWidth, expectedWidth });
    expect(geometry.stageWidth).toBeCloseTo(expectedWidth, 1);
    expect(geometry.artboardWidth).toBeCloseTo(expectedWidth, 1);
    if (expectedWidth > geometry.clientWidth) expect(geometry.scrollWidth).toBeGreaterThan(geometry.clientWidth);
  }
});
