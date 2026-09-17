import { act, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SiteRenderer from "./PageBuilder.siteRenderer";

const position = (x, y, width, height) => ({
  desktop: { x, y, width, height },
  tablet: { x, y, width, height },
  mobile: { x, y, width, height },
});

describe("SiteRenderer collision padding", () => {
  beforeEach(() => {
    globalThis.ResizeObserver = class ResizeObserver {
      observe() {}
      disconnect() {}
    };
    vi.stubGlobal("requestAnimationFrame", () => 1);
    vi.stubGlobal("cancelAnimationFrame", () => {});
  });

  it("keeps resolved resize geometry out of the responsive and collision passes", () => {
    const snapshot = {
      heading: { x: 39, y: 160, width: 480, height: 110 },
      image: { x: 510, y: 80, width: 220, height: 300 },
    };
    const page = { id: "resize", sections: [{ id: "hero", mode: "direct", layout: { minHeight: 500 }, freeElements: [
      { id: "heading", type: "heading", styles: {}, position: position(20, 100, 400, 100) },
      { id: "image", type: "image", styles: {}, position: position(500, 80, 200, 300) },
    ] }] };
    const props = { project: { theme: {} }, activePage: page, viewportMode: "tablet", renderElement: (element) => <div>{element.id}</div> };
    const view = render(<SiteRenderer {...props} interactionPositionsBySection={{ hero: snapshot }} />);
    const heading = view.container.querySelector('[data-builder-element-id="heading"]');
    const image = view.container.querySelector('[data-builder-element-id="image"]');
    expect(heading.style.width).toBe("480px");
    expect(heading.style.transform).toBe("translate3d(39px, 160px, 0)");
    const imageBefore = image.style.cssText;
    view.rerender(<SiteRenderer {...props} interactionPositionsBySection={{ hero: { ...snapshot, heading: { ...snapshot.heading, width: 420 } } }} />);
    expect(heading.style.width).toBe("420px");
    expect(heading.style.transform).toBe("translate3d(39px, 160px, 0)");
    expect(image.style.cssText).toBe(imageBefore);
  });

  it("renders overlapping saved mobile elements in stable order with proportional 15% gaps", () => {
    const page = {
      id: "mobile-page",
      sections: [{
        id: "content",
        mode: "direct",
        layout: { width: "full", minHeight: 120 },
        freeElements: [
          { id: "heading", type: "heading", styles: {}, position: position(20, 30, 350, 90) },
          { id: "copy", type: "text", styles: {}, position: position(20, 80, 350, 100) },
          { id: "card", type: "card", styles: {}, position: position(20, 150, 350, 220) },
        ],
      }],
    };
    const before = JSON.stringify(page);
    const view = render(
      <SiteRenderer
        project={{ theme: {} }}
        activePage={page}
        viewportMode="mobile"
        renderElement={(element) => <div>{element.id}</div>}
      />
    );

    const heading = view.container.querySelector('[data-builder-element-id="heading"]');
    const copy = view.container.querySelector('[data-builder-element-id="copy"]');
    const card = view.container.querySelector('[data-builder-element-id="card"]');
    const section = view.container.querySelector(".site-section");

    expect(heading.classList.contains("is-intrinsic-height")).toBe(true);
    expect(copy.classList.contains("is-intrinsic-height")).toBe(true);
    expect(Number(heading.dataset.logicalY)).toBe(30);
    expect(Number(copy.dataset.logicalY)).toBe(134);
    expect(Number(card.dataset.logicalY)).toBe(249);
    expect(section.style.minHeight).toBe("517px");
    expect(JSON.stringify(page)).toBe(before);
  });

  it("preserves converted flow spacing while still resolving actual overlap", () => {
    const view = render(
      <SiteRenderer
        project={{ theme: {} }}
        activePage={{ id: "converted", sections: [{
          id: "flow", mode: "direct",
          layout: { preserveAuthoredSpacing: true },
          freeElements: [
            { id: "heading", type: "heading", styles: {}, directWidthMode: "fixed", position: position(40, 20, 400, 100) },
            { id: "copy", type: "text", styles: {}, position: position(40, 125, 400, 60) },
            { id: "overlap", type: "text", styles: {}, position: position(40, 160, 400, 60) },
          ],
        }] }}
        renderElement={(element) => <div>{element.id}</div>}
      />
    );
    expect(view.container.querySelector('[data-builder-element-id="copy"]').dataset.logicalY).toBe("125");
    expect(view.container.querySelector('[data-builder-element-id="overlap"]').dataset.logicalY).toBe("185");
  });

  it("keeps a saved two-column row aligned", () => {
    const page = {
      id: "columns-page",
      sections: [{
        id: "columns",
        mode: "direct",
        layout: { width: "full" },
        freeElements: [
          { id: "left", type: "card", styles: {}, position: position(10, 40, 170, 200) },
          { id: "right", type: "card", styles: {}, position: position(200, 40, 170, 200) },
        ],
      }],
    };
    const view = render(
      <SiteRenderer
        project={{ theme: {} }}
        activePage={page}
        viewportMode="mobile"
        renderElement={(element) => <div>{element.id}</div>}
      />
    );

    expect(view.container.querySelector('[data-builder-element-id="left"]').dataset.logicalY).toBe("40");
    expect(view.container.querySelector('[data-builder-element-id="right"]').dataset.logicalY).toBe("40");
  });

  it("allows only the editorial image button to grow with its content", () => {
    const page = {
      id: "image-card-page",
      sections: [{
        id: "cards",
        mode: "direct",
        layout: { width: "full" },
        freeElements: [
          { id: "editorial", type: "imageButton", imageButtonVariant: "editorialCard", styles: {}, position: position(20, 40, 380, 240) },
          { id: "image-only", type: "imageButton", styles: {}, position: position(20, 320, 380, 180) },
        ],
      }],
    };
    const view = render(
      <SiteRenderer
        project={{ theme: {} }}
        activePage={page}
        viewportMode="desktop"
        renderElement={(element) => <div>{element.id}</div>}
      />
    );

    expect(view.container.querySelector('[data-builder-element-id="editorial"]').classList.contains("is-intrinsic-height")).toBe(false);
    expect(view.container.querySelector('[data-builder-element-id="image-only"]').classList.contains("is-intrinsic-height")).toBe(false);
  });

  it("repairs an oversized saved divider frame to its compact interaction height", () => {
    const page = {
      id: "divider-page",
      sections: [{
        id: "divider-section",
        mode: "direct",
        layout: { width: "full" },
        freeElements: [
          { id: "line", type: "thinDivider", styles: {}, position: position(20, 80, 350, 120) },
        ],
      }],
    };
    const view = render(
      <SiteRenderer
        project={{ theme: {} }}
        activePage={page}
        viewportMode="desktop"
        renderElement={(element) => <div>{element.id}</div>}
      />
    );

    expect(view.container.querySelector('[data-builder-element-id="line"]').dataset.logicalHeight)
      .toBe("24");
  });

  it("uses wrapped text height before padding the next element", async () => {
    const observerCallbacks = [];
    const animationCallbacks = [];
    globalThis.ResizeObserver = class ResizeObserver {
      constructor(callback) { observerCallbacks.push(callback); }
      observe() {}
      disconnect() {}
    };
    vi.stubGlobal("requestAnimationFrame", (callback) => {
      animationCallbacks.push(callback);
      return animationCallbacks.length;
    });
    const page = {
      id: "wrapped-page",
      sections: [{
        id: "wrapped",
        mode: "direct",
        layout: { width: "full" },
        freeElements: [
          { id: "heading", type: "heading", styles: {}, position: position(20, 20, 350, 60) },
          { id: "copy", type: "text", styles: {}, position: position(20, 100, 350, 80) },
        ],
      }],
    };
    const view = render(
      <SiteRenderer
        project={{ theme: {} }}
        activePage={page}
        viewportMode="mobile"
        renderElement={(element) => <div>{element.id}</div>}
      />
    );
    const headingContent = view.container.querySelector(
      '[data-builder-element-id="heading"] > .direct-element-content'
    );
    Object.defineProperty(headingContent, "scrollHeight", { configurable: true, value: 150 });
    Object.defineProperty(headingContent, "offsetHeight", { configurable: true, value: 150 });

    await act(async () => {
      observerCallbacks.forEach((callback) => callback([]));
      animationCallbacks.splice(0).forEach((callback) => callback());
    });

    const heading = view.container.querySelector('[data-builder-element-id="heading"]');
    const copy = view.container.querySelector('[data-builder-element-id="copy"]');
    expect(heading.dataset.logicalHeight).toBe("150");
    expect(copy.dataset.logicalY).toBe("193");
  });

  it("pins authored under-text artwork but treats standalone images as responsive media", () => {
    const breakpointPosition = (desktop, tablet, mobile = tablet) => ({ desktop, tablet, mobile });
    const page = {
      id: "artwork-page",
      sections: [{
        id: "artwork",
        mode: "direct",
        layout: { width: "full" },
        freeElements: [
          {
            id: "copy",
            type: "text",
            styles: {},
            position: breakpointPosition(
              { x: 100, y: 100, width: 500, height: 180 },
              { x: 39, y: 100, width: 690, height: 180 }
            ),
          },
          {
            id: "art",
            type: "image",
            styles: {},
            position: breakpointPosition(
              { x: 240, y: 60, width: 400, height: 400 },
              { x: 280, y: 120, width: 360, height: 360 }
            ),
          },
          {
            id: "photo",
            type: "image",
            styles: {},
            position: breakpointPosition(
              { x: 40, y: 700, width: 300, height: 200 },
              { x: 20, y: 700, width: 300, height: 200 }
            ),
          },
        ],
      }],
    };
    const view = render(
      <SiteRenderer
        project={{ theme: {} }}
        activePage={page}
        viewportMode="tablet"
        renderElement={(element) => <div>{element.id}</div>}
      />
    );

    const art = view.container.querySelector('[data-builder-element-id="art"]');
    const photo = view.container.querySelector('[data-builder-element-id="photo"]');
    expect(art.classList.contains("is-behind-text")).toBe(true);
    expect(Number(art.dataset.logicalX)).toBeCloseTo(153.6, 3);
    expect(Number(art.dataset.logicalY)).toBeCloseTo(74.4, 3);
    expect(Number(art.dataset.logicalWidth)).toBeCloseTo(256, 3);
    expect(photo.classList.contains("is-behind-text")).toBe(false);
    expect(Number(photo.dataset.logicalWidth)).toBeCloseTo(427.8, 2);
  });
});
