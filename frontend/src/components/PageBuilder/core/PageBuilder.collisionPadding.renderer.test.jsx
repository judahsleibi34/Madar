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
