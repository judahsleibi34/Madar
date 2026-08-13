import { describe, expect, it } from "vitest";

import { viewports } from "./PageBuilder.constants";
import {
  DEFAULT_CAPABILITIES,
  getResponsiveCapabilities,
  withAutoResponsiveOverride,
  withManualResponsiveOverride,
} from "./PageBuilder.responsiveCapabilities";
import { rectanglesIntersect } from "./PageBuilder.spatialIndex";
import { solveResponsiveSection } from "./PageBuilder.responsiveSolver";
import { resolvePageResponsiveLayout } from "./PageBuilder.responsiveLayout";

const modes = ["desktop", "tablet", "mobile"];

const createElement = (id, type = "future-component", positionFactory = null) => ({
  id,
  type,
  name: id,
  position: Object.fromEntries(modes.map((mode) => {
    const width = viewports[mode];
    const position = positionFactory?.(mode, width) || { x: 24, y: 24, width: 160, height: 72 };
    return [mode, position];
  })),
});

const createGeneratedSection = (count) => ({
  id: `section-${count}`,
  mode: "direct",
  layout: { minHeight: 120 },
  freeElements: Array.from({ length: count }, (_, index) => createElement(
    `element-${String(index).padStart(3, "0")}`,
    index % 7 === 0 ? "heading" : index % 5 === 0 ? "image" : "future-component",
    (_mode, width) => {
      const usable = width - 48;
      const columns = Math.max(1, Math.floor((usable + 12) / 112));
      const column = index % columns;
      const row = Math.floor(index / columns);
      return {
        x: 24 + column * 112,
        y: 24 + row * 92,
        width: 100,
        height: 72,
      };
    }
  )),
});

const expectSolidGeometryValid = (layout) => {
  const ids = Object.keys(layout.elementRects);
  ids.forEach((id) => {
    const rect = layout.elementRects[id];
    const policy = layout.capabilities[id].collisionPolicy;
    if (policy !== "solid") return;
    expect(rect.x).toBeGreaterThanOrEqual(0);
    expect(rect.x + rect.width).toBeLessThanOrEqual(layout.layoutWidth + 0.01);
  });
  ids.forEach((id, index) => {
    if (layout.capabilities[id].collisionPolicy !== "solid") return;
    ids.slice(index + 1).forEach((otherId) => {
      if (layout.capabilities[otherId].collisionPolicy !== "solid") return;
      expect(rectanglesIntersect(layout.elementRects[id], layout.elementRects[otherId])).toBe(false);
    });
  });
};

describe("responsive capability registry", () => {
  it("gives unknown future components a safe generic contract", () => {
    const capabilities = getResponsiveCapabilities({ type: "component-added-next-year" });
    expect(capabilities).toMatchObject({
      sizingX: DEFAULT_CAPABILITIES.sizingX,
      sizingY: DEFAULT_CAPABILITIES.sizingY,
      collisionPolicy: "solid",
      canShrinkX: true,
      canGrowY: true,
    });
  });

  it("excludes explicitly layered backgrounds from solid collisions", () => {
    expect(getResponsiveCapabilities({ type: "image", layer: "behindText" }).collisionPolicy)
      .toBe("background");
  });
});

describe("deterministic responsive section solver", () => {
  it("satisfies bounds and collision invariants across seeded arbitrary layouts", () => {
    const randomForSeed = (seedValue) => {
      let state = seedValue >>> 0;
      return () => {
        state = (state * 1664525 + 1013904223) >>> 0;
        return state / 0x100000000;
      };
    };
    for (let seed = 1; seed <= 10; seed += 1) {
      const random = randomForSeed(seed);
      const elements = Array.from({ length: 20 }, (_, index) => createElement(
        `seed-${seed}-element-${index}`,
        index % 4 === 0 ? "future-component" : index % 3 === 0 ? "text" : "image",
        (_mode, width) => {
          const elementWidth = 80 + Math.floor(random() * Math.min(260, width - 48));
          return {
            x: Math.floor(random() * Math.max(1, width - elementWidth)),
            y: Math.floor(random() * 600),
            width: elementWidth,
            height: 48 + Math.floor(random() * 180),
          };
        }
      ));
      const section = { id: `seed-section-${seed}`, mode: "direct", layout: {}, freeElements: elements };
      [360, 517, 767, 913, 1199].forEach((layoutWidth) => {
        const layout = solveResponsiveSection({
          section,
          layoutWidth,
          viewportMode: layoutWidth <= 600 ? "mobile" : layoutWidth <= 1024 ? "tablet" : "desktop",
        });
        expectSolidGeometryValid(layout);
      });
    }
  });

  it.each([2, 20, 200])("keeps %i arbitrary elements in bounds and non-overlapping", (count) => {
    const section = createGeneratedSection(count);
    [360, 390, 480, 600, 601, 768, 900, 1024, 1025, 1200].forEach((layoutWidth) => {
      const viewportMode = layoutWidth <= 600 ? "mobile" : layoutWidth <= 1024 ? "tablet" : "desktop";
      const first = solveResponsiveSection({ section, layoutWidth, viewportMode });
      const second = solveResponsiveSection({ section, layoutWidth, viewportMode });
      expect(second).toEqual(first);
      expectSolidGeometryValid(first);
    });
  });

  it("never mutates source schema while solving or applying measurements", () => {
    const section = createGeneratedSection(20);
    const project = {
      responsiveLayout: { mode: "smart", engineVersion: 1 },
      pages: [{ id: "page", sections: [section] }],
    };
    const before = JSON.stringify(project);
    resolvePageResponsiveLayout({
      project,
      page: project.pages[0],
      viewportMode: "tablet",
      layoutWidth: 700,
      measurements: { [section.id]: { "element-000": 420 } },
      changedElementIds: ["element-000"],
    });
    expect(JSON.stringify(project)).toBe(before);
  });

  it("keeps manual overrides authoritative and diagnoses unsatisfiable manual collisions", () => {
    let first = createElement("first", "text");
    let second = createElement("second", "text");
    first = withManualResponsiveOverride(first, "tablet", { x: 40, y: 40, width: 300, height: 100 });
    second = withManualResponsiveOverride(second, "tablet", { x: 100, y: 80, width: 300, height: 100 });
    const layout = solveResponsiveSection({
      section: { id: "manual", mode: "direct", layout: {}, freeElements: [first, second] },
      layoutWidth: 768,
      viewportMode: "tablet",
    });
    expect(layout.elementRects.first).toEqual({ x: 40, y: 40, width: 300, height: 100 });
    expect(layout.elementRects.second).toEqual({ x: 100, y: 80, width: 300, height: 100 });
    expect(layout.diagnostics.some((item) => item.code === "unresolved_manual_collision")).toBe(true);
  });

  it("uses an Auto tombstone instead of restoring legacy tablet geometry", () => {
    const source = createElement("reset", "text");
    source.position.desktop = { x: 300, y: 90, width: 400, height: 100 };
    source.position.tablet = { x: 10, y: 10, width: 100, height: 50 };
    const reset = withAutoResponsiveOverride(source, "tablet");
    const layout = solveResponsiveSection({
      section: { id: "reset-section", mode: "direct", layout: {}, freeElements: [reset] },
      layoutWidth: 768,
      viewportMode: "tablet",
    });
    expect(layout.elementRects.reset.x).toBeCloseTo(192, 3);
    expect(layout.elementRects.reset.width).toBeCloseTo(256, 3);
  });

  it("does not make an arbitrary geometry jump at 600/601 or 1024/1025", () => {
    const section = createGeneratedSection(6);
    [[600, 601], [1024, 1025]].forEach(([beforeWidth, afterWidth]) => {
      const before = solveResponsiveSection({
        section,
        layoutWidth: beforeWidth,
        viewportMode: beforeWidth <= 600 ? "mobile" : "tablet",
      });
      const after = solveResponsiveSection({
        section,
        layoutWidth: afterWidth,
        viewportMode: afterWidth <= 1024 ? "tablet" : "desktop",
      });
      Object.keys(before.elementRects).forEach((id) => {
        const first = before.elementRects[id];
        const second = after.elementRects[id];
        expect(Math.abs(second.x - first.x)).toBeLessThan(4);
        expect(Math.abs(second.width - first.width)).toBeLessThan(4);
        expect(Math.abs(second.y - first.y)).toBeLessThan(4);
      });
    });
  });

  it("cascades intrinsic height growth through the downstream closure", () => {
    const first = createElement("first", "text", () => ({ x: 24, y: 20, width: 320, height: 80 }));
    const second = createElement("second", "future-component", () => ({ x: 24, y: 120, width: 320, height: 80 }));
    const section = { id: "dynamic", mode: "direct", layout: { minHeight: 120 }, freeElements: [first, second] };
    const initial = solveResponsiveSection({ section, layoutWidth: 768, viewportMode: "tablet" });
    const grown = solveResponsiveSection({
      section,
      layoutWidth: 768,
      viewportMode: "tablet",
      measurements: { first: 300 },
      changedElementIds: ["first"],
      previousResolved: initial,
    });
    expect(grown.elementRects.first.height).toBe(300);
    expect(grown.elementRects.second.y).toBeGreaterThanOrEqual(336);
    expect(grown.affectedElementIds).toContain("second");
    expect(grown.rect.height).toBeGreaterThan(initial.rect.height);
    expectSolidGeometryValid(grown);
  });

  it("meets a conservative 200-element cold performance budget without all-pairs candidates", () => {
    const section = createGeneratedSection(200);
    const started = performance.now();
    const layout = solveResponsiveSection({ section, layoutWidth: 913, viewportMode: "tablet" });
    const elapsed = performance.now() - started;
    expect(elapsed).toBeLessThan(1500);
    expect(layout.relationships.candidatePairCount).toBeLessThan(200 * 30);
    expectSolidGeometryValid(layout);

    const incrementalStarted = performance.now();
    const incremental = solveResponsiveSection({
      section,
      layoutWidth: 913,
      viewportMode: "tablet",
      measurements: { "element-199": 180 },
      changedElementIds: ["element-199"],
      previousResolved: layout,
    });
    const incrementalElapsed = performance.now() - incrementalStarted;
    expect(incrementalElapsed).toBeLessThan(1000);
    const unaffectedIds = Object.keys(layout.elementRects).filter((id) =>
      !incremental.affectedElementIds.includes(id)
    );
    expect(unaffectedIds.length).toBeGreaterThan(0);
    unaffectedIds.forEach((id) => {
      expect(incremental.elementRects[id]).toEqual(layout.elementRects[id]);
    });
  });
});

describe("page-level resolved layout", () => {
  it("returns null for legacy projects and identical editor/live geometry for smart inputs", () => {
    const page = { id: "page", sections: [createGeneratedSection(20)] };
    expect(resolvePageResponsiveLayout({
      project: { responsiveLayout: { mode: "legacy", engineVersion: 1 } },
      page,
      viewportMode: "tablet",
      layoutWidth: 700,
    })).toBeNull();

    const project = { responsiveLayout: { mode: "smart", engineVersion: 1 }, pages: [page] };
    const editor = resolvePageResponsiveLayout({ project, page, viewportMode: "tablet", layoutWidth: 768 });
    const live = resolvePageResponsiveLayout({ project, page, viewportMode: "tablet", layoutWidth: 768 });
    expect(live).toEqual(editor);
    expect(editor.referenceWidth).toBe(768);
    expect(editor.layoutWidth).toBe(768);
    expect(editor.presentationZoom).toBe(1);
  });
});
