import { describe, expect, it } from "vitest";

import { getBuilderFreeElementStyle } from "./PageBuilder.styles";

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
});
