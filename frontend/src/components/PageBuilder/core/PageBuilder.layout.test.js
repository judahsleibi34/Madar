import { describe, expect, it } from "vitest";

import { getMovedElementPosition } from "./PageBuilder.layout";

describe("page builder scaled canvas coordinates", () => {
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
});
