import { describe, expect, it } from "vitest";

import {
  commitDirectElementGroupInteraction,
  commitDirectElementInteraction,
} from "./PageBuilder.layout";

const element = (id, x = 20) => ({
  id,
  type: "future-component",
  position: {
    desktop: { x, y: 20, width: 100, height: 60 },
    tablet: { x, y: 20, width: 100, height: 60 },
    mobile: { x, y: 20, width: 100, height: 60 },
  },
});

const section = (elements) => ({
  id: "section",
  mode: "direct",
  layout: { minHeight: 200, minHeightByViewport: {} },
  freeElements: elements,
});

describe("smart responsive manual persistence", () => {
  it("keeps legacy commits byte-compatible when smart mode is disabled", () => {
    const source = [section([element("one")])];
    const result = commitDirectElementInteraction(source, {
      elementId: "one",
      sourceSectionId: "section",
      viewportName: "tablet",
      previewPosition: { x: 50, y: 70, width: 120, height: 80 },
      previewSectionHeight: 240,
    });
    expect(result[0].freeElements[0].responsive).toBeUndefined();
    expect(result[0].freeElements[0].position.tablet).toEqual({ x: 50, y: 70, width: 120, height: 80 });
  });

  it("writes an explicit per-mode override only at smart pointer-up commit", () => {
    const source = [section([element("one")])];
    const rect = { x: 50, y: 70, width: 120, height: 80 };
    const result = commitDirectElementInteraction(source, {
      elementId: "one",
      sourceSectionId: "section",
      viewportName: "tablet",
      previewPosition: rect,
      previewSectionHeight: 240,
      smartResponsive: true,
    });
    expect(result[0].freeElements[0].responsive.overrides.tablet).toEqual({ mode: "manual", rect });
    expect(result[0].freeElements[0].responsive.overrides.mobile).toBeUndefined();
    expect(source[0].freeElements[0].responsive).toBeUndefined();
  });

  it("persists every element in a smart group move without touching other modes", () => {
    const source = [section([element("one"), element("two", 140)])];
    const previewPositions = {
      one: { x: 60, y: 90, width: 100, height: 60 },
      two: { x: 180, y: 90, width: 100, height: 60 },
    };
    const result = commitDirectElementGroupInteraction(source, {
      sourceSectionId: "section",
      viewportName: "mobile",
      previewPositions,
      previewSectionHeight: 240,
      smartResponsive: true,
    });
    result[0].freeElements.forEach((item) => {
      expect(item.responsive.overrides.mobile).toEqual({
        mode: "manual",
        rect: previewPositions[item.id],
      });
      expect(item.responsive.overrides.tablet).toBeUndefined();
    });
  });
});
