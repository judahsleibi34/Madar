import { describe, expect, it, vi } from "vitest";

import {
  commitDirectElementGroupInteraction,
  commitDirectElementInteraction,
  getGroupDragPreviewPositions,
  getMarqueeSelectionIds,
  getPositionCollectionBounds,
  getSmartGuideSnap,
} from "./PageBuilder.layout";

const originalFrame = { x: 20, y: 30, width: 240, height: 100 };
const sections = [{
  id: "section-a",
  layout: { minHeight: 600, minHeightByViewport: { desktop: 600 } },
  freeElements: [{
    id: "element-a",
    position: { desktop: originalFrame },
  }],
}];

describe("direct interaction commit safety", () => {
  it("selects every component touched by a marquee rectangle", () => {
    const elements = [
      { id: "heading", position: { desktop: { x: 20, y: 20, width: 300, height: 80 } } },
      { id: "image", position: { desktop: { x: 400, y: 300, width: 300, height: 240 } } },
      { id: "button", position: { desktop: { x: 900, y: 700, width: 160, height: 48 } } },
    ];

    expect(getMarqueeSelectionIds(elements, "desktop", {
      startX: 350,
      startY: 250,
      currentX: 750,
      currentY: 580,
    })).toEqual(["image"]);
  });
  it("moves a selected group without changing its internal spacing", () => {
    const previewPositions = getGroupDragPreviewPositions({
      startPositions: {
        "element-a": { x: 20, y: 30, width: 240, height: 100 },
        "element-b": { x: 300, y: 180, width: 200, height: 80 },
      },
      primaryElementId: "element-a",
      primaryPreview: { x: 100, y: 90, width: 240, height: 100 },
      bounds: { x: 0, y: 0, width: 1200, height: 600 },
    });

    expect(previewPositions["element-a"]).toMatchObject({ x: 100, y: 90 });
    expect(previewPositions["element-b"]).toMatchObject({ x: 380, y: 240 });
  });

  it("centers the complete selected group instead of its primary component", () => {
    const startPositions = {
      "element-a": { x: 100, y: 40, width: 100, height: 60 },
      "element-b": { x: 300, y: 140, width: 100, height: 60 },
    };
    const initialBounds = getPositionCollectionBounds(startPositions);
    const snap = getSmartGuideSnap({
      candidate: initialBounds,
      canvasWidth: 800,
      canvasHeight: 600,
      threshold: 200,
    });
    const previewPositions = getGroupDragPreviewPositions({
      startPositions,
      primaryElementId: "element-a",
      primaryPreview: {
        ...startPositions["element-a"],
        x: startPositions["element-a"].x + snap.position.x - initialBounds.x,
      },
      bounds: { x: 0, y: 0, width: 800, height: 600 },
    });
    const finalBounds = getPositionCollectionBounds(previewPositions);

    expect(finalBounds.x + finalBounds.width / 2).toBe(400);
    expect(previewPositions["element-b"].x - previewPositions["element-a"].x).toBe(200);
  });
  it("commits all selected positions in one section update", () => {
    const source = [{
      ...sections[0],
      freeElements: [
        sections[0].freeElements[0],
        { id: "element-b", position: { desktop: { x: 300, y: 180, width: 200, height: 80 } } },
      ],
    }];
    const committed = commitDirectElementGroupInteraction(source, {
      sourceSectionId: "section-a",
      viewportName: "desktop",
      previewSectionHeight: 760,
      previewPositions: {
        "element-a": { x: 100, y: 90, width: 240, height: 100 },
        "element-b": { x: 380, y: 240, width: 200, height: 80 },
      },
    });

    expect(committed[0].freeElements.map((element) => element.position.desktop.x))
      .toEqual([100, 380]);
    expect(committed[0].layout.minHeightByViewport.desktop).toBe(760);
  });
  it("commits geometry and persists downward canvas growth on release", () => {
    const updateSections = vi.fn((updater) => updater(sections));
    let transientFrame = originalFrame;

    for (let pointerMove = 1; pointerMove <= 20; pointerMove += 1) {
      transientFrame = { ...transientFrame, x: 20 + pointerMove, y: 30 + pointerMove };
    }
    expect(updateSections).not.toHaveBeenCalled();

    const committed = updateSections((currentSections) =>
      commitDirectElementInteraction(currentSections, {
        elementId: "element-a",
        previewPosition: transientFrame,
        previewSectionHeight: 720,
        sourceSectionId: "section-a",
        viewportName: "desktop",
      })
    );

    expect(updateSections).toHaveBeenCalledTimes(1);
    expect(committed[0].freeElements[0].position.desktop).toEqual(transientFrame);
    expect(committed[0].layout.minHeightByViewport.desktop).toBe(720);
  });

  it("does not shrink an existing section on commit", () => {
    const committed = commitDirectElementInteraction(sections, {
      elementId: "element-a",
      previewPosition: { ...originalFrame, y: 40 },
      previewSectionHeight: 300,
      sourceSectionId: "section-a",
      viewportName: "desktop",
    });

    expect(committed[0].layout.minHeight).toBe(600);
    expect(committed[0].layout.minHeightByViewport.desktop).toBe(600);
  });

  it("stores interaction metadata with the resized element", () => {
    const committed = commitDirectElementInteraction(sections, {
      elementId: "element-a",
      previewPosition: { ...originalFrame, width: 500 },
      previewSectionHeight: 720,
      sourceSectionId: "section-a",
      viewportName: "desktop",
      elementUpdates: { directWidthMode: "fixed" },
    });

    expect(committed[0].freeElements[0].directWidthMode).toBe("fixed");
    expect(committed[0].freeElements[0].position.desktop.width).toBe(500);
  });
});
