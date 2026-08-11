import { describe, expect, it } from "vitest";

import {
  getBuilderElementStyle,
  getBuilderFreeElementStyle,
  getDirectCanvasScaleStyles,
  getDirectElementFrameStyle,
  getResponsiveDirectCanvasStyles,
} from "./PageBuilder.styles";
import { viewports } from "./PageBuilder.constants";
import { createElement, createPosition } from "./PageBuilder.factories";
import {
  directElementHeight,
  getDirectElementMinimumSize,
  getMetricMinimumHeight,
} from "./PageBuilder.layout";

describe("getDirectCanvasScaleStyles", () => {
  it("scales the logical frame, its content, and its visible section as one unit", () => {
    const styles = getDirectCanvasScaleStyles({
      logicalWidth: 1200,
      logicalHeight: 1600,
      scale: 0.8,
    });

    expect(styles.section).toEqual({ minHeight: "1280px" });
    expect(styles.shell).toEqual({ width: "960px", height: "1280px" });
    expect(styles.frame).toEqual({
      width: "1200px",
      minHeight: "1600px",
      transform: "scale(0.8)",
      transformOrigin: "top left",
    });
  });

  it("never enlarges a logical canvas above its authored size", () => {
    const styles = getDirectCanvasScaleStyles({
      logicalWidth: 1200,
      logicalHeight: 600,
      scale: 1.5,
    });

    expect(styles.shell.width).toBe("1200px");
    expect(styles.frame.transform).toBe("scale(1)");
  });
});

describe("getResponsiveDirectCanvasStyles", () => {
  it("fills the runtime width without scaling the frame child content", () => {
    const styles = getResponsiveDirectCanvasStyles({ logicalHeight: 900, scale: 1.5 });

    expect(styles.section).toEqual({ minHeight: "1350px" });
    expect(styles.shell).toEqual({ width: "100%", height: "1350px" });
    expect(styles.frame).toEqual({ width: "100%", minHeight: "1350px" });
  });
});

describe("getBuilderElementStyle", () => {
  it("does not let legacy inline button colors override the website theme", () => {
    const style = getBuilderElementStyle({
      element: {
        id: "button-1",
        type: "button",
        styles: {
          backgroundColor: "var(--action-primary, var(--theme-primary))",
          color: "#ffffff",
          borderRadius: "8px",
          fontSize: "14px",
        },
      },
      selected: { type: "", id: "" },
      carouselElementTypes: new Set(),
      getElementPlacementMargins: () => ({}),
      getElementLayoutWidth: () => undefined,
      normalizeElementAlignSelf: () => undefined,
    });

    expect(style.backgroundColor).toBeUndefined();
    expect(style.color).toBeUndefined();
    expect(style["--builder-element-bg"]).toBe("transparent");
    expect(style["--builder-element-color"]).toBe("inherit");
    expect(style.borderRadius).toBe("8px");
    expect(style.fontSize).toBe("14px");
  });

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
  it("keeps every direct component inside desktop, tablet, and mobile canvases", () => {
    const componentTypes = [
      "heading",
      "text",
      "button",
      "image",
      "card",
      "carousel",
      "list",
      "divider",
      "thinDivider",
      "embed",
      "metric",
      "loginBlock",
      "registrationBlock",
      "formBlock",
      "reservationBlock",
    ];

    componentTypes.forEach((type) => {
      const element = createElement(type);
      Object.entries(viewports).forEach(([viewportName, viewportWidth]) => {
        const base = createPosition()[viewportName];
        const minimum = getDirectElementMinimumSize(element);
        const position = {
          ...base,
          width: Math.max(base.width, minimum.width),
          height: Math.max(directElementHeight(element), minimum.height),
        };
        const style = getDirectElementFrameStyle({
          element,
          position,
          viewportWidth,
          sectionHeight: 1000,
          getMetricMinimumHeight,
          getDirectElementMinimumSize,
        });

        expect(Number.parseFloat(style.width), `${type} width at ${viewportName}`).toBeLessThanOrEqual(viewportWidth);
        expect(Number.parseFloat(style.maxWidth), `${type} max-width at ${viewportName}`).toBeLessThanOrEqual(viewportWidth);
        expect(minimum.width, `${type} minimum width at ${viewportName}`).toBeLessThanOrEqual(viewportWidth);
      });
    });
  });

  it("uses the same unscaled geometry contract consumed by Go Live", () => {
    const element = {
      id: "heading-1",
      type: "heading",
      position: { desktop: { x: 80, y: 120, width: 560, height: 96 } },
    };
    const sharedOptions = {
      element,
      getMetricMinimumHeight: () => 80,
      getDirectElementMinimumSize: () => ({ width: 120, height: 48 }),
    };
    const builderStyle = getBuilderFreeElementStyle({
      ...sharedOptions,
      viewport: "desktop",
      activePage: { sections: [{ id: "section-1" }] },
      viewports: { desktop: 1200 },
      createPosition: () => element.position,
      findElementLocation: () => ({ sectionId: "section-1" }),
      getSectionCanvasHeight: () => 720,
      canvasScale: 1,
    });
    const liveStyle = getDirectElementFrameStyle({
      ...sharedOptions,
      position: element.position.desktop,
      viewportWidth: 1200,
      sectionHeight: 720,
      canvasScale: 1,
    });

    expect(liveStyle).toEqual(builderStyle);
    expect(builderStyle.width).toBe("1120px");
    expect(builderStyle.maxWidth).toBe("1120px");
  });

  it("preserves a heading width after the user explicitly resizes it", () => {
    const style = getDirectElementFrameStyle({
      element: {
        id: "heading-fixed",
        type: "heading",
        directWidthMode: "fixed",
      },
      position: { x: 80, y: 120, width: 560, height: 96 },
      viewportWidth: 1200,
      sectionHeight: 720,
      getMetricMinimumHeight: () => 80,
      getDirectElementMinimumSize: () => ({ width: 120, height: 48 }),
    });

    expect(style.width).toBe("560px");
    expect(style.maxWidth).toBe("1120px");
  });

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
