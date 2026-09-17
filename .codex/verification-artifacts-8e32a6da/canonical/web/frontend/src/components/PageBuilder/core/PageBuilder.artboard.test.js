import { describe, expect, it } from "vitest";

import {
  getArtboardElementPosition,
  getArtboardLogicalWidth,
  getEditorCameraStageWidth,
  getFitPresentationZoom,
  getLiveArtboardProfile,
  getLiveArtboardViewportMode,
  logicalRectToPhysicalRect,
  physicalRectToLogicalRect,
} from "./PageBuilder.artboard";

describe("artboard geometry", () => {
  it("keeps viewport modes on fixed logical CSS widths", () => {
    expect(getArtboardLogicalWidth("desktop")).toBe(1200);
    expect(getArtboardLogicalWidth("tablet")).toBe(768);
    expect(getArtboardLogicalWidth("mobile")).toBe(390);
  });

  it("uses the visitor CSS-pixel viewport only for live mode selection", () => {
    expect(getLiveArtboardViewportMode(480)).toBe("mobile");
    expect(getLiveArtboardViewportMode(600)).toBe("mobile");
    expect(getLiveArtboardViewportMode(601)).toBe("tablet");
    expect(getLiveArtboardViewportMode(768)).toBe("tablet");
    expect(getLiveArtboardViewportMode(1024)).toBe("tablet");
    expect(getLiveArtboardViewportMode(1025)).toBe("desktop");
  });

  it("never upscales authored artboards at intentional crossovers", () => {
    const beforeMobileCrossover = getLiveArtboardProfile(600);
    const afterMobileCrossover = getLiveArtboardProfile(601);
    const beforeDesktopCrossover = getLiveArtboardProfile(1024);
    const afterDesktopCrossover = getLiveArtboardProfile(1025);

    expect(beforeMobileCrossover.presentationZoom).toBe(1);
    expect(afterMobileCrossover.logicalWidth * afterMobileCrossover.presentationZoom).toBeCloseTo(601);
    expect(beforeDesktopCrossover.presentationZoom).toBe(1);
    expect(afterDesktopCrossover.logicalWidth * afterDesktopCrossover.presentationZoom).toBeCloseTo(1025);
  });

  it("snapshots live logical, physical, and normalized geometry across production widths", () => {
    const widths = [1920, 1440, 1200, 1025, 1024, 769, 768, 601, 600, 481, 480, 390, 360];
    const savedByMode = {
      desktop: { x: 100, y: 80, width: 320, height: 90 },
      tablet: { x: 40, y: 50, width: 280, height: 80 },
      mobile: { x: 20, y: 30, width: 200, height: 70 },
    };

    const matrix = widths.map((availableWidth) => {
      const profile = getLiveArtboardProfile(availableWidth);
      const savedElementRect = savedByMode[profile.viewportMode];
      const physicalArtboardWidth = profile.logicalWidth * profile.presentationZoom;
      const artboardOrigin = { x: Math.max(0, (availableWidth - physicalArtboardWidth) / 2), y: 0 };
      const physicalElementRect = logicalRectToPhysicalRect(savedElementRect, profile.presentationZoom, artboardOrigin);
      const normalizedElementRect = physicalRectToLogicalRect(physicalElementRect, profile.presentationZoom, artboardOrigin);
      return {
        availableWidth,
        ...profile,
        artboardRect: {
          ...artboardOrigin,
          width: physicalArtboardWidth,
          height: 500 * profile.presentationZoom,
        },
        sectionRect: {
          ...artboardOrigin,
          width: physicalArtboardWidth,
          height: 500 * profile.presentationZoom,
        },
        fullBleedWidth: availableWidth,
        savedElementRect,
        physicalElementRect,
        normalizedElementRect,
      };
    });

    matrix.forEach((entry) => {
      Object.keys(entry.savedElementRect).forEach((key) => {
        expect(entry.normalizedElementRect[key]).toBeCloseTo(entry.savedElementRect[key], 8);
      });
      expect(entry.artboardRect).toEqual(entry.sectionRect);
      expect(entry.artboardRect.width).toBeLessThanOrEqual(entry.availableWidth);
      expect(entry.fullBleedWidth).toBe(entry.availableWidth);
    });
    expect(matrix.map(({ availableWidth, viewportMode, logicalWidth, presentationZoom }) => ({
      availableWidth,
      viewportMode,
      logicalWidth,
      presentationZoom: Number(presentationZoom.toFixed(6)),
    }))).toMatchInlineSnapshot(`
      [
        {
          "availableWidth": 1920,
          "logicalWidth": 1200,
          "presentationZoom": 1,
          "viewportMode": "desktop",
        },
        {
          "availableWidth": 1440,
          "logicalWidth": 1200,
          "presentationZoom": 1,
          "viewportMode": "desktop",
        },
        {
          "availableWidth": 1200,
          "logicalWidth": 1200,
          "presentationZoom": 1,
          "viewportMode": "desktop",
        },
        {
          "availableWidth": 1025,
          "logicalWidth": 1200,
          "presentationZoom": 0.854167,
          "viewportMode": "desktop",
        },
        {
          "availableWidth": 1024,
          "logicalWidth": 768,
          "presentationZoom": 1,
          "viewportMode": "tablet",
        },
        {
          "availableWidth": 769,
          "logicalWidth": 768,
          "presentationZoom": 1,
          "viewportMode": "tablet",
        },
        {
          "availableWidth": 768,
          "logicalWidth": 768,
          "presentationZoom": 1,
          "viewportMode": "tablet",
        },
        {
          "availableWidth": 601,
          "logicalWidth": 768,
          "presentationZoom": 0.782552,
          "viewportMode": "tablet",
        },
        {
          "availableWidth": 600,
          "logicalWidth": 390,
          "presentationZoom": 1,
          "viewportMode": "mobile",
        },
        {
          "availableWidth": 481,
          "logicalWidth": 390,
          "presentationZoom": 1,
          "viewportMode": "mobile",
        },
        {
          "availableWidth": 480,
          "logicalWidth": 390,
          "presentationZoom": 1,
          "viewportMode": "mobile",
        },
        {
          "availableWidth": 390,
          "logicalWidth": 390,
          "presentationZoom": 1,
          "viewportMode": "mobile",
        },
        {
          "availableWidth": 360,
          "logicalWidth": 390,
          "presentationZoom": 0.923077,
          "viewportMode": "mobile",
        },
      ]
    `);
  });

  it("fits without enlarging and normalizes physical diagnostics", () => {
    expect(getFitPresentationZoom(600, 1200)).toBe(0.5);
    expect(getFitPresentationZoom(1800, 1200)).toBe(1);
    expect(physicalRectToLogicalRect({ x: 10, y: 20, width: 300, height: 200 }, 0.5))
      .toEqual({ x: 20, y: 40, width: 600, height: 400 });
  });

  it("sizes the editor camera from only logical width and editor zoom", () => {
    const schema = Object.freeze({
      pages: Object.freeze([{ id: "page_1", geometry: Object.freeze({ x: 0, width: 1200 }) }]),
    });
    const before = JSON.stringify(schema);
    const cases = [
      ["Fit narrow", 1200, getFitPresentationZoom(720, 1200), 720],
      ["90%", 1200, 0.9, 1080],
      ["100%", 1200, 1, 1200],
      ["125%", 1200, 1.25, 1500],
    ];

    cases.forEach(([, logicalWidth, editorZoom, expectedWidth]) => {
      expect(getEditorCameraStageWidth(logicalWidth, editorZoom)).toBe(expectedWidth);
    });
    expect(JSON.stringify(schema)).toBe(before);
  });

  it("scales only missing legacy positions into the selected artboard", () => {
    const position = getArtboardElementPosition({
      position: { desktop: { x: 120, y: 60, width: 600, height: 100 } },
    }, "mobile");
    expect(position).toEqual({ x: 39, y: 19.5, width: 195, height: 32.5 });
  });
});
