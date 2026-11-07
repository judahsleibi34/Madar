import { expect, test } from "@playwright/test";
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { evaluateVisual, loadEvidenceWriter, observeAcademy, packetDirectory, semanticChecks, sourceIdentity, writeReviewPacket } from "./academy-visual-contract.mjs";

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

// Exercise the canonical hosted entry without DNS or public-server access.
// Every asset is served from the existing loopback Vite server; APIs are fixtures.
const hostedOrigin = "https://artboard-test.madarportal.com";
test.beforeEach(async ({ page, baseURL }) => {
  page.on("console", (message) => { if (message.type() === "error") console.log("browser-error", message.text()); });
  page.on("pageerror", (error) => console.log("page-error", error.message));
  page.on("requestfailed", (request) => console.log("request-failed", request.url(), request.failure()?.errorText));
  await page.routeWebSocket("**/*", (socket) => socket.close());
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (![hostedOrigin, baseURL].includes(url.origin)) { console.log("blocked-origin", url.origin + url.pathname); return route.abort(); }
    if (url.pathname.startsWith("/api/")) {
      console.log("unmocked-api", url.pathname);
      return route.fulfill({ status: 503, json: { error: "Unmocked test API" } });
    }
    const response = await route.fetch({
      url: new URL(url.pathname + url.search, baseURL).href,
      maxRedirects: 0,
    });
    await route.fulfill({ response });
  });
});

test.afterEach(async ({ page }) => {
  console.log("fixture-diagnostic", JSON.stringify(await page.evaluate(() => {
    const move = document.querySelector(".direct-move-handle");
    const box = move?.getBoundingClientRect();
    const center = box ? [box.x + box.width / 2, box.y + box.height / 2] : null;
    return { url: location.href, viewport: [innerWidth, innerHeight], dpr: devicePixelRatio,
      move: box?.toJSON(), center, hits: center ? document.elementsFromPoint(...center).map(node => node.className) : [] };
  })));
});

test("published layout uses saved artboards, full bleed, and controlled snapshots", async ({ page }, testInfo) => {
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
        visitor: { logged_in: false, user: null },
        project: {
          site_id: "artboard-site",
          site_identifier: "artboard-test",
          project_id: "artboard-project",
          publication_key: "artboard-publication-1",
          published_schema: publishedSchema,
          published_version: 1,
          published_revision: 1,
        },
      },
    });
  });

  await page.setViewportSize({ width: 1200, height: 900 });
  await page.goto(hostedOrigin + "/", { waitUntil: "networkidle" });
  await expect(page).toHaveURL(hostedOrigin + "/");
  // The real hosted runtime intentionally shows its loading screen for 10 s.
  await expect(page.locator(".site-renderer-camera")).toBeVisible({ timeout: 20_000 });
  await page.evaluate(() => document.fonts.ready);
  const captures = [];
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
      const image = await artboard.screenshot({
        animations: "disabled",
        path: testInfo.outputPath(`current-artboard-${width}.png`),
      });
      captures.push({ width, image });
      console.log(JSON.stringify({
        viewport: page.viewportSize(), url: page.url(), geometry,
        browser: page.context().browser().version(), platform: process.platform,
        deviceScaleFactor: await page.evaluate(() => devicePixelRatio),
        capturePolicy: "whole artboard locator; natural layout height; animations disabled",
        fontsReady: await page.evaluate(() => document.fonts.status === "loaded"),
        snapshotReference: testInfo.snapshotPath(`legacy-artboard-${width}.png`),
      }));
    }
  }

  // Preserve every screenshot assertion while reporting all missing references.
  for (const { width, image } of captures) {
    expect.soft(image).toMatchSnapshot(`legacy-artboard-${width}.png`);
  }
});

test("editor viewport scrolls an exact camera stage and does not clip boundary overlays", async ({ page }) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.setContent(`
    <link rel="stylesheet" href="/src/styles/index.css">
    <div class="page-builder" style="margin:48px">
      <main class="builder-canvas-shell editor-viewport camera-manual" style="width:500px;height:420px;box-sizing:border-box">
        <div style="padding:48px;width:max-content">
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

const academyFixture = (language, mode) => {
  const arabic = language === "ar";
  const button = { type: "button", styles: { fontSize: "18px" }, backgroundColor: "#245678", textColor: "#FFFFFF", hoverBackgroundColor: "#345678", hoverTextColor: "#FFFFFF", borderColor: "#123456" };
  const elements = [
    { id: "academy-heading", type: "heading", content: arabic ? "أكاديمية الاختبار" : "Academy parity", styles: { fontSize: "32px" } },
    { id: "academy-text", type: "text", content: arabic ? "محتوى تعليمي لاختبار التخطيط والنصوص في الأكاديمية." : "Published learning content checks wrapping and authored presentation.", styles: { fontSize: "20px" } },
    { ...button, id: "academy-action", content: arabic ? "المزيد" : "Read more", action: { type: "goToPage", pageId: "details" } },
    { ...button, id: "academy-disabled", content: arabic ? "غير متاح" : "Unavailable", disabled: true },
    { id: "academy-courses", type: "academyCourseCollection", academy: { heading: "Courses" } },
  ];
  const section = { id: "academy-section", rows: [{ id: "r", columns: [{ id: "c", elements }] }] };
  const theme = mode === "dark" ? { mode, background: "#101820", surface: "#182430", softSurface: "#203040", text: "#FFFFFF", muted: "#BBCBDD", headerBackground: "#182430" } : { mode };
  return {
    site: { subdomain: "artboard-test", brand: "Parity Academy", theme, academy_registration: "open", course_label: "Course", section_label: "Level", lesson_label: "Lesson", instructor_label: "Instructor" },
    authenticated: false, courses: [], plans: [],
    landing: { name: "Parity Academy", theme, defaultPageId: "home", siteChrome: { showHeader: true, showFooter: true, brand: "Parity Academy", footerStoreName: "Parity Academy", rights: "Parity footer" }, pages: [
      { id: "home", name: "Home", slug: "/", isDefault: true, sections: [section] },
      { id: "details", name: "Details", slug: "/details", sections: [{ id: "details-section", rows: [{ id: "dr", columns: [{ id: "dc", elements: [{ id: "details-heading", type: "heading", content: "Details destination" }] }] }] }] },
    ] },
  };
};

for (const width of [390, 768, 1200]) {
  for (const language of ["en", "ar"]) {
    for (const mode of ["light", "dark"]) {
      test(`Academy parity ${width} ${language} ${mode}`, async ({ page }, testInfo) => {
        const baselineDirectory = process.env.MADAR_ACADEMY_BASELINE_DIR;
        expect(baselineDirectory, "Provide the reviewed Academy evidence directory").toBeTruthy();
        const evidenceRoot = path.resolve(process.env.HOME, "madar-qa-evidence/phase-38.1/original-source-rollback");
        expect(path.resolve(baselineDirectory).startsWith("/tmp/") || path.resolve(baselineDirectory).startsWith(evidenceRoot + path.sep)).toBe(true);
        const recording = process.env.MADAR_ACADEMY_CAPTURE_BASELINE === "1";
        if (recording) {
          expect(readFileSync("src/components/ELearning/AcademyBuilderLanding.jsx", "utf8")).toContain('import "../../styles/admin/PageBuilder/index.css"');
          mkdirSync(baselineDirectory, { recursive: true });
        }
        expect(recording, "Qualification must never replace references").toBe(false);
        const writer = await loadEvidenceWriter(process.env.MADAR_ATOMIC_EVIDENCE_WRITER);
        const repository = path.resolve("../..");
        const initialSource = sourceIdentity(repository);
        const browserSession = await page.context().browser().newBrowserCDPSession();
        const browserIdentity = { version: await browserSession.send("Browser.getVersion"), system: await browserSession.send("SystemInfo.getInfo"), platform: process.platform, arch: process.arch };
        await browserSession.detach();
        const captures = [];
        const fixture = academyFixture(language, mode);
        const fixtureHash = createHash("sha256").update(JSON.stringify(fixture)).digest("hex");
        await page.addInitScript((lang) => localStorage.setItem("madar.language", lang), language);
        await page.route("**/api/public/academies/artboard-test", route => route.fulfill({ json: fixture }));
        await page.setViewportSize({ width, height: 900 });
        await page.goto(hostedOrigin + "/academy/", { waitUntil: "networkidle" });
        await expect(page.locator(".academy-builder-landing")).toBeVisible();
        await expect(page.locator(".academy-presentation")).toHaveAttribute("dir", language === "ar" ? "rtl" : "ltr");
        await expect(page.locator(".built-site-header")).toBeVisible();
        await expect(page.locator(".built-site-footer")).toBeVisible();
        await page.evaluate(() => document.fonts.ready);
        const action = page.getByRole("button", { name: language === "ar" ? "المزيد" : "Read more", exact: true });
        const disabled = page.getByRole("button", { name: language === "ar" ? "غير متاح" : "Unavailable", exact: true });
        await expect(disabled).toBeDisabled();
        const capture = async (state) => {
          // Two frames can still sample the authored 160ms hover transition.
          // Measure its natural settled state, matching the screenshot state.
          await page.evaluate(() => document.fonts.ready);
          await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
          await page.waitForFunction(() => document.getAnimations().every(animation =>
            animation.playState === "finished" || animation.playState === "idle"
          ), null, { timeout: 5000 });
          const name = `academy-${width}-${language}-${mode}-${state}`;
          const metrics = await page.evaluate(() => {
            const selectors = [".academy-presentation", ".academy-builder-landing", ".built-site-header", ".built-site-footer", ".builder-element-heading", ".builder-element-text", ".builder-element-button"];
            return { scrollWidth: document.documentElement.scrollWidth, scrollHeight: document.documentElement.scrollHeight, nodes: selectors.flatMap(selector => [...document.querySelectorAll(selector)].map(node => {
              const css = getComputedStyle(node), rect = node.getBoundingClientRect();
              return { selector, text: node.textContent, rect: [rect.x, rect.y, rect.width, rect.height], styles: Object.fromEntries(["color", "backgroundColor", "fontFamily", "fontSize", "lineHeight", "direction", "padding", "margin", "border", "borderRadius", "boxShadow", "outline", "opacity", "cursor"].map(key => [key, css[key]])) };
            })) };
          });
          const observations = await page.evaluate(observeAcademy);
          const png = await page.screenshot({ fullPage: true, animations: "disabled", path: testInfo.outputPath(`${name}.png`) });
          const metadata = { fixtureHash, width, height: 900, language, mode, state, browser: page.context().browser().version(), dpr: await page.evaluate(() => devicePixelRatio), fontsReady: await page.evaluate(() => document.fonts.status), metrics };
          writeFileSync(testInfo.outputPath(`${name}.json`), JSON.stringify(metadata, null, 2));
          const pngPath = path.join(baselineDirectory, `${name}.png`), jsonPath = path.join(baselineDirectory, `${name}.json`);
          if (recording) {
            writeFileSync(pngPath, png, { flag: "wx" });
            writeFileSync(jsonPath, JSON.stringify(metadata, null, 2), { flag: "wx" });
          } else {
            captures.push({ name, state, reference: readFileSync(pngPath), actual: png, expected: JSON.parse(readFileSync(jsonPath, "utf8")), metadata, observations });
          }
        };
        const interactions = { disabled: true, disabledClick: false, keyboardFocus: false, enterNavigation: false };
        let workflowError;
        try {
          await capture("default");
          await action.hover();
          await capture("hover");
          await page.mouse.move(0, 0);
          for (let step = 0; step < 30 && !await action.evaluate(node => node === document.activeElement); step += 1) await page.keyboard.press("Tab");
          await expect(action).toBeFocused();
          interactions.keyboardFocus = true;
          await capture("focus");
          // Native HTMLElement.click on a disabled control must not navigate.
          const beforeDisabled = page.url();
          await disabled.evaluate(node => node.click());
          expect(page.url()).toBe(beforeDisabled);
          interactions.disabledClick = true;
          await page.keyboard.press("Enter");
          await expect(page).toHaveURL(hostedOrigin + "/academy/details");
          await expect(page.getByText("Details destination", { exact: true })).toBeVisible();
          interactions.enterNavigation = true;
        } catch (error) { workflowError = error; }
        const finalSource = sourceIdentity(repository);
        const evaluated = [];
        for (const shot of captures) {
          const identity = { source: finalSource, fixture: fixtureHash, browser: browserIdentity, scenario: shot.name };
          const expectedIdentity = { ...identity, source: initialSource };
          const checks = [...semanticChecks(shot.observations, { width, language, mode, state: shot.state }),
            ...Object.entries(interactions).map(([name, pass]) => ({ name, pass })),
            { name: "complete workflow", pass: !workflowError && captures.length === 3 }];
          const result = evaluateVisual({ ...shot, identity, expectedIdentity, checks });
          const packet = await writeReviewPacket({ directory: packetDirectory(process.env.MADAR_VISUAL_EVIDENCE_ROOT, shot.name), writer, result, ...shot, interactions });
          evaluated.push({ shot, result, packet });
        }
        for (const { shot, result, packet } of evaluated) {
          console.log(JSON.stringify({ academyVisual: shot.name, status: result.status, packet }));
          expect(result.status, `${shot.name}: mandatory guards; packet ${packet.directory}`).not.toBe("FAIL");
          expect(shot.metadata).toEqual(shot.expected);
          // Soft only to collect every state/scenario; this still FAILS the runner.
          expect.soft(shot.actual.equals(shot.reference), `${shot.name}: exact browser pixels must match original CSS baseline; ${result.status}; ${packet.directory}`).toBe(true);
        }
        if (workflowError) throw workflowError;
      });
    }
  }
}
