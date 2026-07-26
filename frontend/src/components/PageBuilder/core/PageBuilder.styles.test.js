import { describe, expect, it } from "vitest";

import { getBuilderElementStyle, getBuilderFreeElementStyle } from "./PageBuilder.styles";

describe("getBuilderElementStyle", () => {
  it("preserves independent image scale variables", () => {
    const style = getBuilderElementStyle({
      element: {
        id: "image-1",
        type: "image",
        styles: { "--image-scale": "1.75" },
      },
      selected: { type: "element", id: "image-1" },
      carouselElementTypes: new Set(),
      getElementPlacementMargins: () => ({}),
      getElementLayoutWidth: () => undefined,
      normalizeElementAlignSelf: () => undefined,
    });

    expect(style["--image-scale"]).toBe("1.75");
  });
});

describe("getBuilderFreeElementStyle", () => {
  it("moves a recovered element inside the canvas without collapsing its width", () => {
    const element = {
      id: "text-1",
      type: "text",
      position: {
        desktop: { x: 1100, y: 40, width: 380, height: 96 },
      },
    };

    const style = getBuilderFreeElementStyle({
      element,
      viewport: "desktop",
      activePage: { sections: [{ id: "section-1" }] },
      viewports: { desktop: 1200 },
      createPosition: () => ({
        desktop: { x: 0, y: 0, width: 380, height: 96 },
      }),
      findElementLocation: () => ({ sectionId: "section-1" }),
      getSectionCanvasHeight: () => 600,
      getMetricMinimumHeight: () => 80,
      getDirectElementMinimumSize: () => ({ width: 120, height: 48 }),
      canvasScale: 0.5,
    });

    expect(style.width).toBe("190px");
    expect(style.transform).toBe("translate3d(410px, 20px, 0)");
    expect(style.maxWidth).toBe("190px");
  });

  it("keeps a behind-text image below selected text boundaries", () => {
    const style = getBuilderFreeElementStyle({
      element: {
        id: "image-1",
        type: "image",
        layer: "behindText",
        position: { desktop: { x: 0, y: 0, width: 400, height: 200 } },
      },
      viewport: "desktop",
      activePage: { sections: [{ id: "section-1" }] },
      viewports: { desktop: 1200 },
      createPosition: () => ({ desktop: { x: 0, y: 0, width: 400, height: 200 } }),
      findElementLocation: () => ({ sectionId: "section-1" }),
      getSectionCanvasHeight: () => 600,
      getMetricMinimumHeight: () => 80,
      getDirectElementMinimumSize: () => ({ width: 120, height: 48 }),
    });

    expect(style.zIndex).toBe(0);
  });

  it("keeps normal direct elements above behind-text images", () => {
    const style = getBuilderFreeElementStyle({
      element: {
        id: "button-1",
        type: "button",
        position: { desktop: { x: 20, y: 20, width: 160, height: 48 } },
      },
      viewport: "desktop",
      activePage: { sections: [{ id: "section-1" }] },
      viewports: { desktop: 1200 },
      createPosition: () => ({ desktop: { x: 0, y: 0, width: 240, height: 80 } }),
      findElementLocation: () => ({ sectionId: "section-1" }),
      getSectionCanvasHeight: () => 800,
      getMetricMinimumHeight: () => 80,
      getDirectElementMinimumSize: () => ({ width: 120, height: 48 }),
    });

    expect(style.zIndex).toBe(1);
  });
});
