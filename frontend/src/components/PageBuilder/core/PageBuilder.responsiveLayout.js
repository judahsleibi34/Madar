import { viewports } from "./PageBuilder.constants";
import { normalizeArtboardViewportMode } from "./PageBuilder.artboard";
import { isSmartResponsiveProject } from "./PageBuilder.responsiveCapabilities";
import { getResponsiveCapabilities } from "./PageBuilder.responsiveCapabilities";
import { solveResponsiveSection } from "./PageBuilder.responsiveSolver";

const resolvedPageCache = new Map();
export const RESPONSIVE_SOLVER_BUDGETS = Object.freeze({
  20: Object.freeze({ coldMs: 100, incrementalMs: 60 }),
  50: Object.freeze({ coldMs: 250, incrementalMs: 120 }),
  100: Object.freeze({ coldMs: 600, incrementalMs: 250 }),
  200: Object.freeze({ coldMs: 1500, incrementalMs: 500 }),
});
const now = () => globalThis.performance?.now?.() ?? Date.now();
const hashString = (value) => {
  let hash = 2166136261;
  const source = String(value ?? "");
  for (let index = 0; index < source.length; index += 1) {
    hash ^= source.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
};
const signature = (value) => hashString(JSON.stringify(value));

const getPageSignatures = ({
  project,
  page,
  engineVersion,
  layoutWidth,
  contentRevision,
  fontSignature,
  assetState,
  measurements,
}) => {
  const directSections = (page?.sections || []).filter((section) => ["direct", "free"].includes(section?.mode));
  const authoredGeometry = directSections.map((section) => ({
    id: section.id,
    constraints: section.responsive?.constraints,
    minHeight: section.layout?.minHeight,
    elements: (section.freeElements || []).map((element) => ({
      id: element.id,
      type: element.type,
      layer: element.layer,
      position: element.position,
      responsive: element.responsive,
    })),
  }));
  const capabilities = directSections.map((section) =>
    (section.freeElements || []).map((element) => [element.id, getResponsiveCapabilities(element)])
  );
  const content = contentRevision ?? directSections.map((section) =>
    (section.freeElements || []).map((element) => {
      const contentFields = { ...element };
      delete contentFields.position;
      delete contentFields.responsive;
      return [element.id, contentFields];
    })
  );
  return {
    authoredGeometry: signature(authoredGeometry),
    capabilities: signature(capabilities),
    engineVersion: Number(engineVersion) || 0,
    layoutWidth,
    contentRevision: signature(content),
    fontSignature: signature(fontSignature ?? project?.theme?.typography ?? project?.theme?.fonts ?? ""),
    assetState: signature(assetState ?? ""),
    measurements: signature(measurements),
  };
};

export const getSmartLayoutWidth = (availableWidth) =>
  Math.max(1, Math.min(viewports.desktop, Number(availableWidth) || viewports.desktop));

export const resolvePageResponsiveLayout = ({
  project,
  page,
  viewportMode,
  layoutWidth,
  measurements = {},
  changedElementIds = [],
  previousLayout = null,
  transientRectsBySection = {},
  contentRevision,
  fontSignature,
  assetState,
  forceSmart = false,
} = {}) => {
  if ((!forceSmart && !isSmartResponsiveProject(project)) || !page) return null;
  const startedAt = now();
  const mode = normalizeArtboardViewportMode(viewportMode);
  const width = getSmartLayoutWidth(layoutWidth);
  const engineVersion = Number(project?.responsiveLayout?.engineVersion) || 1;
  const signatures = getPageSignatures({
    project,
    page,
    engineVersion,
    layoutWidth: width,
    contentRevision,
    fontSignature,
    assetState,
    measurements,
  });
  const cacheNamespace = `${project?.id || "project"}:${page.id || "page"}`;
  let pageCache = resolvedPageCache.get(cacheNamespace);
  if (!pageCache) {
    pageCache = new Map();
    resolvedPageCache.set(cacheNamespace, pageCache);
  }
  const baseKey = [
    mode,
    signatures.engineVersion,
    signatures.layoutWidth,
    signatures.authoredGeometry,
    signatures.capabilities,
    signatures.contentRevision,
    signatures.fontSignature,
    signatures.assetState,
  ].join(":");
  const cacheKey = `${baseKey}:${signatures.measurements}`;
  const cached = pageCache.get(cacheKey);
  const hasTransientRects = Object.values(transientRectsBySection).some((rects) => Object.keys(rects || {}).length);
  if (cached && !changedElementIds.length && !hasTransientRects) {
    const cachedResult = {
      ...cached.layout,
    };
    Object.defineProperty(cachedResult, "profile", { enumerable: false, value: {
        ...cached.layout.profile,
        cacheHit: true,
        cacheLookupMs: now() - startedAt,
        totalMs: now() - startedAt,
    } });
    return cachedResult;
  }
  const incrementalPrevious = previousLayout || (
    changedElementIds.length
      ? [...pageCache.values()].reverse().find((entry) => entry.baseKey === baseKey)?.layout || null
      : null
  );
  const sections = {};
  const diagnostics = [];
  const sectionProfiles = {};

  (page.sections || []).forEach((section) => {
    if (!['direct', 'free'].includes(section?.mode)) return;
    const resolved = solveResponsiveSection({
      section,
      layoutWidth: width,
      viewportMode: mode,
      measurements: measurements[section.id] || {},
      changedElementIds,
      previousResolved: incrementalPrevious?.sections?.[section.id] || null,
      transientRects: transientRectsBySection[section.id] || {},
      relationshipCacheKey: [
        mode,
        width,
        engineVersion,
        signatures.authoredGeometry,
        signatures.capabilities,
      ].join(":"),
    });
    sections[section.id] = resolved;
    sectionProfiles[section.id] = resolved.profile;
    resolved.diagnostics.forEach((diagnostic) => diagnostics.push({
      ...diagnostic,
      pageId: page.id,
      sectionId: section.id,
    }));
  });

  const assembledAt = now();
  const phaseTotal = (name) => Object.values(sectionProfiles)
    .reduce((total, profile) => total + (Number(profile?.[name]) || 0), 0);
  const layout = {
    engineVersion,
    mode: "smart",
    viewportMode: mode,
    referenceWidth: viewports[mode],
    layoutWidth: width,
    presentationZoom: 1,
    sections,
    diagnostics,
  };
  Object.defineProperty(layout, "profile", { enumerable: false, value: {
      cacheHit: false,
      relationshipInferenceMs: phaseTotal("relationshipInferenceMs"),
      spatialIndexMs: phaseTotal("spatialIndexMs"),
      constraintSolvingMs: phaseTotal("constraintSolvingMs"),
      collisionPropagationMs: phaseTotal("collisionPropagationMs"),
      measurementReconciliationMs: phaseTotal("measurementReconciliationMs"),
      finalLayoutAssemblyMs: (now() - assembledAt) + phaseTotal("finalLayoutAssemblyMs"),
      authoredGeometryMs: phaseTotal("authoredGeometryMs"),
      totalMs: now() - startedAt,
      sections: sectionProfiles,
      signatures,
    } });
  if (!hasTransientRects) pageCache.set(cacheKey, { baseKey, layout });
  if (pageCache.size > 24) pageCache.delete(pageCache.keys().next().value);
  if (resolvedPageCache.size > 48) resolvedPageCache.delete(resolvedPageCache.keys().next().value);
  return layout;
};

export const clearResolvedResponsiveLayoutCache = () => resolvedPageCache.clear();

export const compareLegacyPageWithSmartShadow = ({
  project,
  page,
  viewportMode,
  layoutWidth,
  measurements = {},
  contentRevision,
  fontSignature,
  assetState,
} = {}) => {
  if (!project || !page || isSmartResponsiveProject(project)) return null;
  const smart = resolvePageResponsiveLayout({
    project,
    page,
    viewportMode,
    layoutWidth,
    measurements,
    contentRevision,
    fontSignature,
    assetState,
    forceSmart: true,
  });
  const elements = [];
  (page.sections || []).forEach((section) => {
    const smartSection = smart?.sections?.[section.id];
    (section.freeElements || []).forEach((element) => {
      const legacy = element.position?.[viewportMode] || element.position?.desktop;
      const resolved = smartSection?.elementRects?.[element.id];
      if (!legacy || !resolved) return;
      const displacement = Math.hypot(
        (Number(resolved.x) || 0) - (Number(legacy.x) || 0),
        (Number(resolved.y) || 0) - (Number(legacy.y) || 0)
      );
      elements.push({
        elementId: element.id,
        sectionId: section.id,
        displacement: Math.round(displacement * 1000) / 1000,
        sizeDelta: {
          width: Math.round(((Number(resolved.width) || 0) - (Number(legacy.width) || 0)) * 1000) / 1000,
          height: Math.round(((Number(resolved.height) || 0) - (Number(legacy.height) || 0)) * 1000) / 1000,
        },
      });
    });
  });
  return {
    mode: "shadow",
    displayed: false,
    persisted: false,
    smart,
    elements,
    diagnostics: smart?.diagnostics || [],
    summary: {
      comparedElementCount: elements.length,
      changedElementCount: elements.filter((item) =>
        item.displacement > 0.5 || Math.abs(item.sizeDelta.width) > 0.5 || Math.abs(item.sizeDelta.height) > 0.5
      ).length,
      maximumDisplacement: Math.max(0, ...elements.map((item) => item.displacement)),
      blockingDiagnosticCount: (smart?.diagnostics || []).filter((item) => item.severity === "blocking").length,
    },
  };
};

export const getSmartProjectLayoutDiagnostics = (project, widths = [390, 768, 1200]) => {
  if (!isSmartResponsiveProject(project)) return [];
  const diagnostics = [];
  const modeForWidth = (width) => width <= 600 ? "mobile" : width <= 1024 ? "tablet" : "desktop";
  (project.pages || []).forEach((page) => {
    widths.forEach((layoutWidth) => {
      const resolved = resolvePageResponsiveLayout({
        project,
        page,
        viewportMode: modeForWidth(layoutWidth),
        layoutWidth,
      });
      resolved?.diagnostics.forEach((diagnostic) => diagnostics.push({
        ...diagnostic,
        layoutWidth,
        viewportMode: resolved.viewportMode,
      }));
    });
  });
  return diagnostics;
};
