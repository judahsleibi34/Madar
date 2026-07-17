import { describe, expect, it, vi } from "vitest";

import { commitDirectElementInteraction } from "./PageBuilder.layout";

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
});
