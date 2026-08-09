import { describe, expect, it } from "vitest";

import { viewports } from "./PageBuilder.constants";
import { rectanglesIntersect } from "./PageBuilder.spatialIndex";
import {
  clearResponsiveRelationshipCache,
  solveResponsiveSection,
} from "./PageBuilder.responsiveSolver";
import {
  clearResolvedResponsiveLayoutCache,
  compareLegacyPageWithSmartShadow,
  RESPONSIVE_SOLVER_BUDGETS,
  resolvePageResponsiveLayout,
} from "./PageBuilder.responsiveLayout";
import { withManualResponsiveOverride } from "./PageBuilder.responsiveCapabilities";

const MODES = ["desktop", "tablet", "mobile"];
const modeForWidth = (width) => width <= 600 ? "mobile" : width <= 1024 ? "tablet" : "desktop";

const createElement = (id, index) => ({
  id,
  type: index % 9 === 0 ? "heading" : index % 7 === 0 ? "image" : index % 5 === 0 ? "text" : "future-widget",
  name: id,
  content: `Content ${index}`,
  position: Object.fromEntries(MODES.map((mode) => {
    const width = viewports[mode];
    const usable = width - 48;
    const columns = Math.max(1, Math.floor((usable + 12) / 132));
    const column = index % columns;
    const row = Math.floor(index / columns);
    return [mode, {
      x: 24 + column * 132,
      y: 24 + row * 104,
      width: 120,
      height: 84,
    }];
  })),
});

const createSection = (count, id = `hardening-${count}`) => ({
  id,
  mode: "direct",
  layout: { minHeight: 120 },
  freeElements: Array.from({ length: count }, (_, index) =>
    createElement(`element-${String(index).padStart(3, "0")}`, index)
  ),
});

const assertSolidGeometry = (layout) => {
  const solids = Object.keys(layout.elementRects)
    .filter((id) => layout.capabilities[id].collisionPolicy === "solid");
  solids.forEach((id) => {
    const rect = layout.elementRects[id];
    expect(rect.x).toBeGreaterThanOrEqual(0);
    expect(rect.x + rect.width).toBeLessThanOrEqual(layout.layoutWidth + 0.01);
  });
  solids.forEach((id, index) => solids.slice(index + 1).forEach((otherId) => {
    expect(rectanglesIntersect(layout.elementRects[id], layout.elementRects[otherId])).toBe(false);
  }));
};

const flowSignature = (layout) => [
  Object.entries(layout.elementRects)
    .sort(([, first], [, second]) => (first.y - second.y) || (first.x - second.x))
    .map(([id]) => id)
    .join("|"),
  JSON.stringify(layout.constraintStates),
  layout.reflowedElementIds.join("|"),
].join("::");

describe("responsive performance and invalidation hardening", () => {
  it.each(Object.entries(RESPONSIVE_SOLVER_BUDGETS).map(([count, budget]) => [
    Number(count),
    budget.coldMs,
    budget.incrementalMs,
  ]))("profiles %i elements within cold %ims and incremental %ims budgets", (
    count,
    coldBudget,
    incrementalBudget
  ) => {
    const section = createSection(count);
    clearResponsiveRelationshipCache(section);
    const cold = solveResponsiveSection({
      section,
      layoutWidth: 913,
      viewportMode: "tablet",
      relationshipCacheKey: `cold:${count}`,
    });
    expect(cold.profile.totalMs).toBeLessThan(coldBudget);
    expect(cold.profile.relationshipCacheHit).toBe(false);
    [
      "relationshipInferenceMs",
      "spatialIndexMs",
      "constraintSolvingMs",
      "collisionPropagationMs",
      "measurementReconciliationMs",
      "finalLayoutAssemblyMs",
    ].forEach((phase) => expect(cold.profile[phase]).toBeGreaterThanOrEqual(0));

    const changedId = `element-${String(count - 1).padStart(3, "0")}`;
    const incremental = solveResponsiveSection({
      section,
      layoutWidth: 913,
      viewportMode: "tablet",
      measurements: { [changedId]: 220 },
      changedElementIds: [changedId],
      previousResolved: cold,
      relationshipCacheKey: `cold:${count}`,
    });
    expect(incremental.profile.totalMs).toBeLessThan(incrementalBudget);
    expect(incremental.profile.incremental).toBe(true);
    expect(incremental.profile.relationshipCacheHit).toBe(true);
    expect(incremental.profile.affectedElementCount).toBeLessThanOrEqual(count);
    assertSolidGeometry(incremental);
  });

  it("invalidates final layouts by geometry, capabilities, content, fonts, and assets", () => {
    clearResolvedResponsiveLayoutCache();
    const page = { id: "cache-page", sections: [createSection(20, "cache-section")] };
    const project = {
      id: "cache-project",
      responsiveLayout: { mode: "smart", engineVersion: 1 },
      pages: [page],
    };
    const first = resolvePageResponsiveLayout({
      project, page, viewportMode: "tablet", layoutWidth: 700,
      contentRevision: 1, fontSignature: "font-a", assetState: "ready-a",
    });
    const cached = resolvePageResponsiveLayout({
      project, page, viewportMode: "tablet", layoutWidth: 700,
      contentRevision: 1, fontSignature: "font-a", assetState: "ready-a",
    });
    expect(cached.profile.cacheHit).toBe(true);

    const variants = [
      { contentRevision: 2, fontSignature: "font-a", assetState: "ready-a" },
      { contentRevision: 1, fontSignature: "font-b", assetState: "ready-a" },
      { contentRevision: 1, fontSignature: "font-a", assetState: "ready-b" },
    ];
    variants.forEach((variant) => {
      const result = resolvePageResponsiveLayout({
        project, page, viewportMode: "tablet", layoutWidth: 700, ...variant,
      });
      expect(result.profile.cacheHit).toBe(false);
    });

    const geometryPage = structuredClone(page);
    geometryPage.sections[0].freeElements[0].position.tablet.x += 10;
    const geometryResult = resolvePageResponsiveLayout({
      project: { ...project, pages: [geometryPage] },
      page: geometryPage,
      viewportMode: "tablet",
      layoutWidth: 700,
      contentRevision: 1,
      fontSignature: "font-a",
      assetState: "ready-a",
    });
    expect(geometryResult.profile.signatures.authoredGeometry)
      .not.toBe(first.profile.signatures.authoredGeometry);

    const capabilityPage = structuredClone(page);
    capabilityPage.sections[0].freeElements[0].responsive = {
      capabilities: { minWidth: 210 },
    };
    const capabilityResult = resolvePageResponsiveLayout({
      project: { ...project, pages: [capabilityPage] },
      page: capabilityPage,
      viewportMode: "tablet",
      layoutWidth: 700,
      contentRevision: 1,
      fontSignature: "font-a",
      assetState: "ready-a",
    });
    expect(capabilityResult.profile.signatures.capabilities)
      .not.toBe(first.profile.signatures.capabilities);
  });

  it("uses transient drag geometry without mutating schema and reuses unaffected rectangles", () => {
    const section = createSection(50, "drag-section");
    const beforeSchema = JSON.stringify(section);
    const initial = solveResponsiveSection({
      section,
      layoutWidth: 768,
      viewportMode: "tablet",
      relationshipCacheKey: "drag",
    });
    const moved = solveResponsiveSection({
      section,
      layoutWidth: 768,
      viewportMode: "tablet",
      changedElementIds: ["element-049"],
      transientRects: {
        "element-049": { ...initial.elementRects["element-049"], y: 900 },
      },
      previousResolved: initial,
      relationshipCacheKey: "drag",
    });
    expect(moved.profile.incremental).toBe(true);
    expect(moved.profile.relationshipCacheHit).toBe(true);
    Object.keys(initial.elementRects)
      .filter((id) => !moved.affectedElementIds.includes(id))
      .forEach((id) => expect(moved.elementRects[id]).toEqual(initial.elementRects[id]));
    expect(JSON.stringify(section)).toBe(beforeSchema);
  });
});

describe("continuous responsive stability", () => {
  it("sweeps every CSS pixel from 320 through 1200 without jitter or invalid geometry", () => {
    const section = createSection(20, "width-sweep");
    let previous = null;
    let previousSignature = "";
    let signatureBeforePrevious = "";
    for (let width = 320; width <= 1200; width += 1) {
      const mode = modeForWidth(width);
      const first = solveResponsiveSection({ section, layoutWidth: width, viewportMode: mode });
      const second = solveResponsiveSection({ section, layoutWidth: width, viewportMode: mode });
      expect(second).toEqual(first);
      assertSolidGeometry(first);
      const currentSignature = flowSignature(first);
      if (previous && currentSignature === previousSignature) {
        Object.keys(first.elementRects).forEach((id) => {
          const current = first.elementRects[id];
          const prior = previous.elementRects[id];
          ["x", "y", "width", "height"].forEach((field) => {
            const delta = Math.abs(current[field] - prior[field]);
            if (delta > 6) {
              throw new Error(`Unexpected ${field} displacement of ${delta}px for ${id} at ${width}px`);
            }
          });
        });
      }
      if (signatureBeforePrevious === currentSignature && previousSignature !== currentSignature) {
        throw new Error(`Responsive flow oscillated at width ${width}`);
      }
      signatureBeforePrevious = previousSignature;
      previousSignature = currentSignature;
      previous = first;
    }
  }, 20000);
});

describe("rollout diagnostics", () => {
  it("provides explicit collision actions while keeping the issue blocking", () => {
    let first = createElement("first", 0);
    let second = createElement("second", 1);
    first = withManualResponsiveOverride(first, "tablet", { x: 20, y: 20, width: 300, height: 120 });
    second = withManualResponsiveOverride(second, "tablet", { x: 100, y: 40, width: 300, height: 120 });
    const result = solveResponsiveSection({
      section: { id: "manual-actions", mode: "direct", freeElements: [first, second] },
      layoutWidth: 768,
      viewportMode: "tablet",
    });
    const conflict = result.diagnostics.find((item) => item.code === "unresolved_manual_collision");
    expect(conflict).toMatchObject({
      severity: "blocking",
      elementIds: ["first", "second"],
    });
    expect(conflict.actions).toEqual([
      "move_element",
      "reset_to_auto",
      "mark_intentional_overlay",
      "mark_background",
    ]);
  });

  it("computes legacy shadow geometry without displaying, persisting, or mutating it", () => {
    const page = { id: "legacy-page", sections: [createSection(20, "legacy-section")] };
    const project = {
      id: "legacy-project",
      responsiveLayout: { mode: "legacy", engineVersion: 1 },
      pages: [page],
    };
    const before = JSON.stringify(project);
    const comparison = compareLegacyPageWithSmartShadow({
      project,
      page,
      viewportMode: "tablet",
      layoutWidth: 700,
      fontSignature: "stable-fonts",
      assetState: "ready",
    });
    expect(comparison).toMatchObject({
      mode: "shadow",
      displayed: false,
      persisted: false,
    });
    expect(comparison.summary.comparedElementCount).toBe(20);
    expect(JSON.stringify(project)).toBe(before);
  });
});
