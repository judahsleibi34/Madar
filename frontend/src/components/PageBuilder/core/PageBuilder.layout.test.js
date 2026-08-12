import { describe, expect, it } from "vitest";

import {
  compactDirectSectionAfterElementRemoval,
  constrainResizeToSiblingElements,
  getDirectElementMinimumSize,
  getSectionCanvasHeight,
  getMovedElementPosition,
  getSmartGuideSnap,
  moveElementBehindText,
  moveElementToFront,
  reconcileMeasuredFormBlockPosition,
} from "./PageBuilder.layout";

describe("page builder smart guides", () => {
  it("snaps a moving component to the horizontal canvas center", () => {
    const result = getSmartGuideSnap({
      candidate: { x: 296, y: 40, width: 200, height: 80 },
      canvasWidth: 800,
      canvasHeight: 600,
    });

    expect(result.position.x).toBe(300);
    expect(result.guides).toContainEqual(expect.objectContaining({
      axis: "vertical",
      value: 400,
      kind: "canvas-center",
    }));
  });

  it("centers against the visible canvas intersection instead of the full logical width", () => {
    const result = getSmartGuideSnap({
      candidate: { x: 476, y: 40, width: 200, height: 80 },
      canvasWidth: 1200,
      canvasHeight: 1000,
      canvasBounds: { x: 200, y: 100, width: 760, height: 560 },
    });

    expect(result.position.x).toBe(480);
    expect(result.guides).toContainEqual(expect.objectContaining({
      axis: "vertical",
      value: 580,
      kind: "canvas-center",
    }));
  });
  it("snaps matching component edges", () => {
    const result = getSmartGuideSnap({
      candidate: { x: 103, y: 200, width: 180, height: 70 },
      siblings: [{ x: 100, y: 20, width: 240, height: 80 }],
      canvasWidth: 800,
      canvasHeight: 600,
    });

    expect(result.position.x).toBe(100);
    expect(result.guides.some((guide) => guide.axis === "vertical" && guide.value === 100)).toBe(true);
  });

  it("shows equal spacing when a component is centered between neighbors", () => {
    const result = getSmartGuideSnap({
      candidate: { x: 205, y: 30, width: 100, height: 60 },
      siblings: [
        { x: 0, y: 30, width: 100, height: 60 },
        { x: 410, y: 30, width: 100, height: 60 },
      ],
      canvasWidth: 800,
      canvasHeight: 600,
    });

    expect(result.position.x).toBe(205);
    expect(result.guides.filter((guide) => guide.kind === "spacing")).toHaveLength(2);
    expect(result.guides[0].label).toBe("105px");
  });
});
describe("page builder canvas compaction", () => {
  it("renders a direct canvas from its actual content instead of stale saved height", () => {
    const section = {
      mode: "direct",
      layout: { minHeight: 900, minHeightByViewport: { desktop: 900 } },
      freeElements: [{
        id: "card",
        position: { desktop: { x: 20, y: 24, width: 700, height: 300 } },
      }],
    };

    expect(getSectionCanvasHeight(section, "desktop")).toBe(372);
  });

  it("keeps only a small drop area when a direct canvas is empty", () => {
    expect(getSectionCanvasHeight({
      mode: "direct",
      layout: { minHeight: 900 },
      freeElements: [],
    }, "desktop")).toBe(120);
  });

  it("closes a deleted element gap and shrinks every responsive canvas", () => {
    const makePosition = (y, height) => ({ x: 20, y, width: 600, height });
    const section = {
      id: "section-1",
      mode: "direct",
      layout: {
        minHeight: 900,
        minHeightByViewport: { desktop: 900, tablet: 900, mobile: 900 },
      },
      freeElements: [
        {
          id: "removed",
          position: {
            desktop: makePosition(120, 220),
            tablet: makePosition(120, 220),
            mobile: makePosition(120, 220),
          },
        },
        {
          id: "below",
          position: {
            desktop: makePosition(356, 100),
            tablet: makePosition(356, 100),
            mobile: makePosition(356, 100),
          },
        },
      ],
    };

    const result = compactDirectSectionAfterElementRemoval(section, "removed");

    expect(result.freeElements).toHaveLength(1);
    expect(result.freeElements[0].position.desktop.y).toBe(120);
    expect(result.layout.minHeightByViewport).toEqual({
      desktop: 268,
      tablet: 268,
      mobile: 268,
    });
  });

  it("does not move a side-by-side element that is outside the deleted column", () => {
    const section = {
      mode: "direct",
      layout: { minHeight: 700 },
      freeElements: [
        { id: "removed", position: { desktop: { x: 20, y: 40, width: 220, height: 180 } } },
        { id: "side", position: { desktop: { x: 300, y: 240, width: 220, height: 100 } } },
      ],
    };

    const result = compactDirectSectionAfterElementRemoval(section, "removed");
    expect(result.freeElements[0].position.desktop.y).toBe(240);
  });
});

describe("page builder element layers", () => {
  it("moves an image below every text element while preserving the other layer order", () => {
    const elements = [
      { id: "shape", type: "divider" },
      { id: "heading", type: "heading" },
      { id: "image", type: "image" },
      { id: "text", type: "text" },
    ];

    expect(moveElementBehindText(elements, "image").map((element) => element.id)).toEqual([
      "shape",
      "image",
      "heading",
      "text",
    ]);
    expect(moveElementBehindText(elements, "image")[1]).toMatchObject({
      id: "image",
      layer: "behindText",
    });
  });

  it("leaves layers unchanged when there is no text element", () => {
    const elements = [{ id: "image", type: "image" }, { id: "button", type: "button" }];

    expect(moveElementBehindText(elements, "image")).toBe(elements);
  });

  it("keeps an already layered image stable", () => {
    const elements = [
      { id: "image", type: "image", layer: "behindText" },
      { id: "heading", type: "heading" },
    ];

    expect(moveElementBehindText(elements, "image")).toBe(elements);
  });

  it("moves an unchecked behind-text image to the front and clears its layer", () => {
    const elements = [
      { id: "image", type: "image", layer: "behindText" },
      { id: "heading", type: "heading" },
      { id: "text", type: "text" },
    ];

    const result = moveElementToFront(elements, "image");
    expect(result.map((element) => element.id)).toEqual(["heading", "text", "image"]);
    expect(result[2].layer).toBeUndefined();
  });

  it("allows an image to expand across overlapping text boundaries before layering", () => {
    const candidate = { x: 100, y: 100, width: 700, height: 300 };
    const result = constrainResizeToSiblingElements({
      candidate,
      siblings: [{
        id: "text",
        type: "text",
        position: { desktop: { x: 80, y: 180, width: 760, height: 220 } },
      }],
      selectedElement: { id: "image", type: "image" },
      viewport: "desktop",
      createPosition: () => ({ desktop: { x: 0, y: 0, width: 240, height: 80 } }),
      dragState: { startX: 100, startWidth: 400 },
      canvasWidth: 1200,
    });

    expect(result).toBe(candidate);
  });
});

describe("page builder scaled canvas coordinates", () => {
  it("allows reservation components to resize on both axes", () => {
    expect(getDirectElementMinimumSize({ type: "reservationBlock" })).toEqual({
      width: 320,
      height: 320,
    });
  });

  it("preserves a resized form width while expanding it to fit its content", () => {
    const result = reconcileMeasuredFormBlockPosition({
      current: { x: 72, y: 40, width: 420, height: 300 },
      measuredHeight: 560,
      bounds: { x: 0, y: 0, width: 1200, height: 700 },
      minimumSize: { width: 80, height: 48 },
    });

    expect(result).toMatchObject({
      x: 72,
      y: 40,
      width: 420,
      height: 560,
    });
  });
  it("maps pointer coordinates back into the unscaled canvas", () => {
    const position = { x: 0, y: 0, width: 100, height: 80 };
    const result = getMovedElementPosition({
      selectedElement: {
        position: {
          desktop: position,
          tablet: position,
          mobile: position,
        },
      },
      targetSection: {},
      viewport: "desktop",
      event: { clientX: 300, clientY: 250 },
      frameRect: { left: 100, top: 50 },
      canvasScale: 0.5,
      viewports: { desktop: 1200, tablet: 768, mobile: 390 },
      createPosition: () => ({
        desktop: position,
        tablet: position,
        mobile: position,
      }),
      getSectionCanvasHeight: () => 800,
    });

    expect(result.desktop).toMatchObject({ x: 350, y: 360, width: 100, height: 80 });
  });

  it("keeps an oversized dragged element inside the left canvas edge", async () => {
    const { getDragCandidatePosition } = await import("./PageBuilder.layout");
    const result = getDragCandidatePosition({
      dragState: {
        interaction: "move",
        startX: 40,
        startY: 20,
        startWidth: 500,
        startHeight: 80,
        deltaX: 120,
        deltaY: 0,
      },
      selectedElement: { type: "heading" },
      canvasWidth: 320,
      canvasHeight: 600,
      snapToGrid: (value) => value,
    });

    expect(result.x).toBe(0);
  });

  it("keeps X bounded while allowing a drag to grow below the canvas", async () => {
    const { getDragCandidatePosition } = await import("./PageBuilder.layout");
    const result = getDragCandidatePosition({
      dragState: {
        interaction: "move",
        startX: 250,
        startY: 150,
        startWidth: 100,
        startHeight: 80,
        deltaX: 100,
        deltaY: 220,
      },
      selectedElement: { type: "heading" },
      bounds: { x: 0, y: 0, width: 320, height: 200 },
      allowBottomOverflow: true,
      snapToGrid: (value) => value,
    });

    expect(result).toMatchObject({ x: 220, y: 370, width: 100, height: 80 });
  });
  it("resizes headings at the same rate as the pointer", async () => {
    const { getDragCandidatePosition } = await import("./PageBuilder.layout");
    const result = getDragCandidatePosition({
      dragState: {
        interaction: "resize",
        startX: 40,
        startY: 20,
        startWidth: 300,
        startHeight: 120,
        deltaX: 100,
        deltaY: 100,
      },
      selectedElement: { type: "heading" },
      canvasWidth: 800,
      canvasHeight: 600,
      snapToGrid: (value) => value,
    });

    expect(result).toMatchObject({ width: 400, height: 220 });
  });

  it("resizes images from their width while preserving the media aspect ratio", async () => {
    const { getDragCandidatePosition } = await import("./PageBuilder.layout");
    const result = getDragCandidatePosition({
      dragState: {
        interaction: "resize",
        startX: 20,
        startY: 20,
        startWidth: 400,
        startHeight: 200,
        deltaX: 200,
        deltaY: 50,
      },
      selectedElement: { type: "image", mediaAspectRatio: 2 },
      canvasWidth: 1200,
      canvasHeight: 800,
      allowBottomOverflow: true,
      snapToGrid: (value) => value,
    });

    expect(result).toMatchObject({ width: 600, height: 300 });
  });

  it("resizes images from their height without stretching or compressing them", async () => {
    const { getDragCandidatePosition } = await import("./PageBuilder.layout");
    const result = getDragCandidatePosition({
      dragState: {
        interaction: "resize",
        startX: 20,
        startY: 20,
        startWidth: 400,
        startHeight: 200,
        deltaX: 20,
        deltaY: 100,
      },
      selectedElement: { type: "image", mediaAspectRatio: 2 },
      canvasWidth: 1200,
      canvasHeight: 800,
      allowBottomOverflow: true,
      snapToGrid: (value) => value,
    });

    expect(result).toMatchObject({ width: 600, height: 300 });
    expect(result.width / result.height).toBe(2);
  });

  it("caps image resizing at the builder image width limit", async () => {
    const { getDragCandidatePosition } = await import("./PageBuilder.layout");
    const result = getDragCandidatePosition({
      dragState: {
        interaction: "resize",
        startX: 0,
        startY: 0,
        startWidth: 400,
        startHeight: 200,
        deltaX: 1000,
        deltaY: 0,
      },
      selectedElement: { type: "image", mediaAspectRatio: 2 },
      canvasWidth: 1400,
      canvasHeight: 800,
      allowBottomOverflow: true,
      snapToGrid: (value) => value,
    });

    expect(result).toMatchObject({ width: 960, height: 480 });
  });
});
