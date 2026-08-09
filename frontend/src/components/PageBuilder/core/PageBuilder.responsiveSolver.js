import { viewports } from "./PageBuilder.constants";
import { getArtboardElementPosition, normalizeArtboardViewportMode } from "./PageBuilder.artboard";
import {
  getResponsiveCapabilities,
  getResponsiveOverride,
} from "./PageBuilder.responsiveCapabilities";
import {
  analyzeResponsiveRelationships,
  getAffectedDependencyClosure,
} from "./PageBuilder.relationshipAnalyzer";
import { UniformGridSpatialIndex, rectanglesIntersect } from "./PageBuilder.spatialIndex";

const ANCHORS = Object.freeze([
  { mode: "mobile", width: viewports.mobile },
  { mode: "tablet", width: viewports.tablet },
  { mode: "desktop", width: viewports.desktop },
]);
const EPSILON = 0.01;
const relationshipCache = new WeakMap();
const now = () => globalThis.performance?.now?.() ?? Date.now();

const finite = (value, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const round = (value) => Math.round(finite(value) * 1000) / 1000;

const normalizeRect = (rect, fallback = {}) => ({
  x: round(finite(rect?.x, fallback.x)),
  y: round(finite(rect?.y, fallback.y)),
  width: round(Math.max(1, finite(rect?.width, fallback.width || 240))),
  height: round(Math.max(1, finite(rect?.height, fallback.height || 96))),
});

const interpolate = (first, second, progress) => first + (second - first) * progress;

const interpolateRect = (first, second, progress) => ({
  x: round(interpolate(first.x, second.x, progress)),
  y: round(interpolate(first.y, second.y, progress)),
  width: round(interpolate(first.width, second.width, progress)),
  height: round(interpolate(first.height, second.height, progress)),
});

const scaleRect = (rect, ratio) => ({
  x: round(rect.x * ratio),
  y: round(rect.y * ratio),
  width: round(rect.width * ratio),
  height: round(rect.height),
});

const getAutomaticAnchorRect = (element, mode) => {
  const override = getResponsiveOverride(element, mode);
  if (override?.mode === "manual") return { rect: override.rect, manual: true };

  if (override?.mode === "auto") {
    const desktop = normalizeRect(getArtboardElementPosition(element, "desktop"));
    return {
      rect: scaleRect(desktop, viewports[mode] / viewports.desktop),
      manual: false,
    };
  }

  return {
    rect: normalizeRect(getArtboardElementPosition(element, mode)),
    manual: false,
  };
};

export const getResponsiveSeedRect = (element, layoutWidth, viewportMode) => {
  const width = Math.max(1, Math.min(viewports.desktop, finite(layoutWidth, viewports.desktop)));
  const mode = normalizeArtboardViewportMode(viewportMode);
  const activeOverride = getResponsiveOverride(element, mode);
  if (activeOverride?.mode === "manual") {
    return {
      rect: scaleRect(activeOverride.rect, width / viewports[mode]),
      manual: true,
      sourceMode: mode,
    };
  }

  if (width <= ANCHORS[0].width) {
    const source = getAutomaticAnchorRect(element, "mobile");
    return {
      rect: scaleRect(source.rect, width / ANCHORS[0].width),
      manual: false,
      sourceMode: "mobile",
    };
  }

  if (width >= ANCHORS[ANCHORS.length - 1].width) {
    const source = getAutomaticAnchorRect(element, "desktop");
    return { rect: source.rect, manual: source.manual, sourceMode: "desktop" };
  }

  const upperIndex = ANCHORS.findIndex((anchor) => anchor.width >= width);
  const lower = ANCHORS[upperIndex - 1];
  const upper = ANCHORS[upperIndex];
  const lowerRect = getAutomaticAnchorRect(element, lower.mode);
  const upperRect = getAutomaticAnchorRect(element, upper.mode);
  const progress = (width - lower.width) / (upper.width - lower.width);
  return {
    rect: interpolateRect(lowerRect.rect, upperRect.rect, progress),
    manual: false,
    sourceMode: `${lower.mode}-${upper.mode}`,
  };
};

const fitWidths = (nodes, availableWidth, gap) => {
  const widths = nodes.map((node) => Math.min(node.rect.width, node.capabilities.maxWidth));
  const minimums = nodes.map((node) => Math.min(availableWidth, node.capabilities.minWidth));
  let excess = widths.reduce((sum, value) => sum + value, 0) + gap * Math.max(0, nodes.length - 1) - availableWidth;
  if (excess <= EPSILON) return widths;

  const shrinkable = new Set(nodes.map((node, index) => node.capabilities.canShrinkX ? index : -1).filter((index) => index >= 0));
  while (excess > EPSILON && shrinkable.size) {
    const allowance = [...shrinkable].reduce((sum, index) => sum + Math.max(0, widths[index] - minimums[index]), 0);
    if (allowance <= EPSILON) break;
    [...shrinkable].forEach((index) => {
      const capacity = Math.max(0, widths[index] - minimums[index]);
      const reduction = Math.min(capacity, excess * (capacity / allowance));
      widths[index] -= reduction;
      if (widths[index] <= minimums[index] + EPSILON) shrinkable.delete(index);
    });
    excess = widths.reduce((sum, value) => sum + value, 0) + gap * Math.max(0, nodes.length - 1) - availableWidth;
  }
  return excess <= 0.5 ? widths.map(round) : null;
};

const layoutRows = (nodesById, relationships, bounds, gap) => {
  const states = {};
  relationships.rows.forEach((row) => {
    const nodes = row.elementIds
      .map((id) => nodesById[id])
      .filter((node) => node && node.capabilities.collisionPolicy === "solid");
    if (nodes.length < 2 || nodes.some((node) => node.manual)) {
      states[row.id] = nodes.some((node) => node.manual) ? "manual" : "single";
      return;
    }

    const sourceLeft = Math.min(...nodes.map((node) => node.rect.x));
    const sourceRight = Math.max(...nodes.map((node) => node.rect.x + node.rect.width));
    const outOfBounds = sourceLeft < bounds.x - EPSILON || sourceRight > bounds.x + bounds.width + EPSILON;
    let previousRight = -Infinity;
    const hasOverlap = [...nodes]
      .sort((first, second) => (first.rect.x - second.rect.x) || String(first.id).localeCompare(String(second.id)))
      .some((node) => {
        const overlaps = node.rect.x < previousRight - EPSILON;
        previousRight = Math.max(previousRight, node.rect.x + node.rect.width);
        return overlaps;
      });
    if (!outOfBounds && !hasOverlap) {
      states[row.id] = "authored";
      return;
    }

    const widths = fitWidths(nodes, bounds.width, gap);
    if (widths) {
      states[row.id] = "fit";
      let x = bounds.x;
      const y = Math.max(0, Math.min(...nodes.map((node) => node.rect.y)));
      nodes.forEach((node, index) => {
        node.rect = { ...node.rect, x: round(x), y: round(y), width: widths[index] };
        x += widths[index] + gap;
      });
      return;
    }

    states[row.id] = "stack";
    let y = Math.max(0, Math.min(...nodes.map((node) => node.rect.y)));
    nodes.forEach((node) => {
      const width = Math.min(bounds.width, Math.max(node.capabilities.minWidth, node.rect.width));
      node.rect = {
        ...node.rect,
        x: bounds.x,
        y: round(y),
        width: round(width),
      };
      y += node.rect.height + gap;
    });
  });
  return states;
};

const constrainAutomaticNode = (node, bounds, measuredHeight) => {
  const capabilities = node.capabilities;
  let width = Math.min(capabilities.maxWidth, Math.max(capabilities.minWidth, node.rect.width));
  width = Math.min(width, bounds.width);
  let height = Math.min(capabilities.maxHeight, Math.max(capabilities.minHeight, node.rect.height));
  if (capabilities.sizingY === "aspect" && capabilities.aspectRatio) {
    height = Math.max(capabilities.minHeight, width / capabilities.aspectRatio);
  }
  if (capabilities.canGrowY && measuredHeight > 0) {
    height = Math.max(height, measuredHeight);
  }
  const x = Math.min(Math.max(bounds.x, node.rect.x), bounds.x + bounds.width - width);
  return {
    ...node,
    rect: normalizeRect({ ...node.rect, x, width, height }),
  };
};

const getCachedRelationships = (section, nodes, cacheKey) => {
  if (!section || typeof section !== "object") {
    return { relationships: analyzeResponsiveRelationships(nodes), cacheHit: false };
  }
  let sectionCache = relationshipCache.get(section);
  if (!sectionCache) {
    sectionCache = new Map();
    relationshipCache.set(section, sectionCache);
  }
  if (sectionCache.has(cacheKey)) {
    return { relationships: sectionCache.get(cacheKey), cacheHit: true };
  }
  const relationships = analyzeResponsiveRelationships(nodes);
  sectionCache.set(cacheKey, relationships);
  if (sectionCache.size > 24) sectionCache.delete(sectionCache.keys().next().value);
  return { relationships, cacheHit: false };
};

export const clearResponsiveRelationshipCache = (section) => {
  if (section && typeof section === "object") relationshipCache.delete(section);
};

const resolveMonotonicCollisions = (nodes, gap, diagnostics, activeIds = null) => {
  const index = new UniformGridSpatialIndex(160);
  const solids = nodes.filter((node) => node.capabilities.collisionPolicy === "solid");
  const manual = solids.filter((node) => node.manual).sort((a, b) => String(a.id).localeCompare(String(b.id)));
  const automatic = solids.filter((node) => !node.manual).sort((first, second) =>
    (first.rect.y - second.rect.y) || (first.rect.x - second.rect.x) ||
    (first.sourceIndex - second.sourceIndex) || String(first.id).localeCompare(String(second.id))
  );

  manual.forEach((node) => {
    const collisions = index.query(node.rect).filter((entry) => rectanglesIntersect(node.rect, entry.rect));
    collisions.forEach((entry) => diagnostics.push({
      code: "unresolved_manual_collision",
      elementIds: [entry.id, node.id].sort(),
      severity: "blocking",
      message: "Manual solid elements overlap.",
      actions: ["move_element", "reset_to_auto", "mark_intentional_overlay", "mark_background"],
    }));
    index.insert(node.id, node.rect, node);
  });

  const fixedAutomatic = activeIds
    ? automatic.filter((node) => !activeIds.has(node.id))
    : [];
  const movingAutomatic = activeIds
    ? automatic.filter((node) => activeIds.has(node.id))
    : automatic;
  fixedAutomatic.forEach((node) => index.insert(node.id, node.rect, node));

  movingAutomatic.forEach((node) => {
    let iterations = 0;
    while (iterations <= solids.length) {
      const collisions = index.query(node.rect).filter((entry) => rectanglesIntersect(node.rect, entry.rect));
      if (!collisions.length) break;
      const nextY = Math.max(...collisions.map((entry) => entry.rect.y + entry.rect.height + gap));
      if (nextY <= node.rect.y + EPSILON) break;
      node.rect = { ...node.rect, y: round(nextY) };
      node.reflowed = true;
      iterations += 1;
    }
    if (iterations > solids.length) {
      diagnostics.push({ code: "collision_iteration_limit", elementIds: [node.id] });
    }
    index.insert(node.id, node.rect, node);
  });

  return nodes;
};

export const solveResponsiveSection = ({
  section,
  layoutWidth,
  viewportMode,
  measurements = {},
  changedElementIds = [],
  relationships: suppliedRelationships = null,
  previousResolved = null,
  transientRects = {},
  relationshipCacheKey = "",
  bottomPadding = 48,
} = {}) => {
  const startedAt = now();
  const width = Math.max(1, Math.min(viewports.desktop, finite(layoutWidth, viewports.desktop)));
  const paddingInline = Math.min(24, Math.max(12, finite(section?.responsive?.constraints?.paddingInline, width * 0.02)));
  const gap = Math.max(0, finite(section?.responsive?.constraints?.gap, 16));
  const bounds = { x: paddingInline, y: 0, width: Math.max(1, width - paddingInline * 2) };
  const diagnostics = [];
  const elements = Array.isArray(section?.freeElements) ? section.freeElements : [];
  const authoredNodes = elements.map((element, sourceIndex) => {
    const seed = getResponsiveSeedRect(element, width, viewportMode);
    const capabilities = getResponsiveCapabilities(element);
    return {
      id: element.id,
      element,
      sourceIndex,
      capabilities,
      manual: seed.manual,
      sourceMode: seed.sourceMode,
      rect: normalizeRect(seed.rect),
    };
  });
  const seededAt = now();
  const relationshipResult = suppliedRelationships
    ? { relationships: suppliedRelationships, cacheHit: true }
    : getCachedRelationships(
        section,
        authoredNodes,
        relationshipCacheKey || `${normalizeArtboardViewportMode(viewportMode)}:${round(width)}`
      );
  const relationships = relationshipResult.relationships;
  const changedInSection = changedElementIds.filter((elementId) => elements.some((element) => element.id === elementId));
  const incremental = Boolean(
    previousResolved &&
    previousResolved.layoutWidth === width &&
    previousResolved.viewportMode === normalizeArtboardViewportMode(viewportMode) &&
    changedInSection.length
  );
  const affected = incremental
    ? getAffectedDependencyClosure(relationships, changedInSection)
    : new Set(elements.map((element) => element.id));
  Object.keys(transientRects).forEach((elementId) => affected.add(elementId));
  const reconciliationStartedAt = now();
  const nodes = authoredNodes.map((sourceNode) => {
    const measurement = Math.max(0, finite(measurements[sourceNode.id], 0));
    const previousRect = incremental && !affected.has(sourceNode.id)
      ? previousResolved.elementRects?.[sourceNode.id]
      : null;
    let node = {
      ...sourceNode,
      rect: transientRects[sourceNode.id]
        ? normalizeRect(transientRects[sourceNode.id], sourceNode.rect)
        : previousRect ? normalizeRect(previousRect) : { ...sourceNode.rect },
      manual: Boolean(transientRects[sourceNode.id]) || sourceNode.manual,
      reused: Boolean(previousRect),
    };
    if (!node.manual) node = constrainAutomaticNode(node, bounds, measurement);
    else if (node.capabilities.canGrowY && measurement > node.rect.height) {
      node.rect = { ...node.rect, height: round(measurement) };
    }
    return node;
  });
  const reconciledAt = now();
  const nodesById = Object.fromEntries(nodes.map((node) => [node.id, node]));
  const constraintStates = incremental
    ? { ...(previousResolved?.constraintStates || {}) }
    : layoutRows(nodesById, relationships, bounds, gap);
  const constraintsAt = now();

  nodes.forEach((node) => {
    if (node.capabilities.collisionPolicy !== "solid") return;
    const outside = node.rect.x < -EPSILON || node.rect.x + node.rect.width > width + EPSILON;
    if (outside) {
      diagnostics.push({
        code: node.manual ? "manual_out_of_bounds" : "automatic_out_of_bounds",
        elementIds: [node.id],
        severity: node.manual ? "blocking" : "error",
        message: node.manual
          ? "A manually positioned element is outside the content artboard."
          : "An automatically positioned element is outside the content artboard.",
        actions: node.manual ? ["move_element", "reset_to_auto", "mark_intentional_overlay", "mark_background"] : [],
      });
    }
  });

  resolveMonotonicCollisions(nodes, gap, diagnostics, incremental ? affected : null);
  const collisionsAt = now();
  const solidBottom = nodes
    .filter((node) => node.capabilities.collisionPolicy === "solid")
    .reduce((maximum, node) => Math.max(maximum, node.rect.y + node.rect.height), 0);
  const sourceMinimumHeight = Math.max(
    120,
    finite(section?.responsive?.constraints?.minHeight, 0),
    finite(section?.layout?.minHeight, 0)
  );
  const sectionHeight = round(Math.max(sourceMinimumHeight, solidBottom + bottomPadding));
  nodes.filter((node) => node.reflowed).forEach((node) => affected.add(node.id));

  const result = {
    sectionId: section?.id,
    layoutWidth: width,
    viewportMode: normalizeArtboardViewportMode(viewportMode),
    rect: { x: 0, y: 0, width, height: sectionHeight },
    contentRect: { x: bounds.x, y: 0, width: bounds.width, height: sectionHeight },
    elementRects: Object.fromEntries(nodes.map((node) => [node.id, { ...node.rect }])),
    capabilities: Object.fromEntries(nodes.map((node) => [node.id, node.capabilities])),
    constraintStates,
    reflowedElementIds: nodes.filter((node) => node.reflowed).map((node) => node.id).sort(),
    relationships,
    affectedElementIds: [...affected].sort(),
    diagnostics: diagnostics
      .filter((item, index, values) => index === values.findIndex((candidate) =>
        candidate.code === item.code && candidate.elementIds.join("|") === item.elementIds.join("|")
      )),
  };
  const completedAt = now();
  Object.defineProperty(result, "profile", { enumerable: false, value: {
    authoredGeometryMs: seededAt - startedAt,
    spatialIndexMs: relationshipResult.cacheHit ? 0 : relationships.profile?.spatialIndexMs || 0,
    relationshipInferenceMs: relationshipResult.cacheHit ? 0 : relationships.profile?.relationshipInferenceMs || 0,
    measurementReconciliationMs: reconciledAt - reconciliationStartedAt,
    constraintSolvingMs: constraintsAt - reconciledAt,
    collisionPropagationMs: collisionsAt - constraintsAt,
    finalLayoutAssemblyMs: completedAt - collisionsAt,
    totalMs: completedAt - startedAt,
    relationshipCacheHit: relationshipResult.cacheHit,
    incremental,
    affectedElementCount: affected.size,
    totalElementCount: elements.length,
  } });
  return result;
};
