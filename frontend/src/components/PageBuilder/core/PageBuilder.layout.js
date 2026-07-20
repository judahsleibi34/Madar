import { viewports } from "./PageBuilder.constants";
import { createPosition, createSection } from "./PageBuilder.factories";
import { clampElementToBounds } from "./PageBuilder.bounds";

export const getSectionElements = (section) => {
  const autoElements = (section.rows || []).flatMap((row) =>
    (row.columns || []).flatMap((column) => column.elements || [])
  );

  return [...autoElements, ...(section.freeElements || [])];
};

export const isMetricsSection = (section) =>
  section?.name?.toLowerCase().includes("metric") ||
  getSectionElements(section).some((element) => element.type === "metric");

export const isResponsesSection = (section) =>
  getSectionElements(section).some((element) => element.type === "responsesTable");

export const removeDeprecatedBuilderElements = (section) => ({
  ...section,
  rows: (section.rows || []).map((row) => ({
    ...row,
    columns: (row.columns || []).map((column) => ({
      ...column,
      elements: (column.elements || []).filter((element) => element.type !== "responsesTable"),
    })),
  })),
  freeElements: (section.freeElements || []).filter((element) => element.type !== "responsesTable"),
});

export const hasFormSection = (page) =>
  (page.sections || []).some((section) =>
    getSectionElements(section).some((element) => element.type === "formBlock")
  );

export const removeDuplicateFormHeadings = (section) => ({
  ...section,
  rows: (section.rows || []).map((row) => ({
    ...row,
    columns: (row.columns || []).map((column) => {
      const hasFormBlock = (column.elements || []).some((element) => element.type === "formBlock");
      if (!hasFormBlock) return column;

      return {
        ...column,
        elements: column.elements.filter(
          (element) =>
            !(
              element.type === "heading" &&
              String(element.content || "").trim().toLowerCase() === "submit your information"
            )
        ),
      };
    }),
  })),
});

export const getMetricMinimumHeight = () => 170;

export const getDirectElementMinimumSize = (element) => {
  if (element?.type === "reservationBlock") {
    return { width: 360, height: 770 };
  }

  if (element?.type === "button") {
    return { width: 80, height: 42 };
  }

  if (element?.type === "metric" || element?.type === "list") {
    return { width: 160, height: getMetricMinimumHeight(element) };
  }

  if (element?.type === "loginBlock") {
    return { width: 300, height: 390 };
  }

  if (element?.type === "registrationBlock") {
    return { width: 340, height: 520 };
  }

  return { width: 80, height: 48 };
};

export const reconcileMeasuredFormBlockPosition = ({
  current,
  measuredHeight,
  bounds,
  minimumSize = { width: 80, height: 48 },
}) =>
  clampElementToBounds(
    {
      ...current,
      height: Math.max(Number(current?.height) || 0, Number(measuredHeight) || 0),
    },
    bounds,
    {
      minWidth: minimumSize.width,
      minHeight: minimumSize.height,
      allowBottomOverflow: true,
    }
  );

export const directElementHeight = (element) => {
  if (element?.type === "metric") return getMetricMinimumHeight(element);

  const heights = {
    heading: 112,
    text: 104,
    button: 42,
    image: 260,
    card: 390,
    list: 170,
    formBlock: 460,
    reservationBlock: 770,
    loginBlock: 390,
    registrationBlock: 520,
    carousel: 400,
    carouselCards: 360,
    carouselSplit: 380,
    carouselSpotlight: 420,
    carouselStack: 440,
    carouselEditorial: 400,
    circularGallery: 480,
  };

  return heights[element?.type] || 140;
};

export const estimateFormBlockHeight = (form, viewportName = "desktop") => {
  const sections = Array.isArray(form?.sections) ? form.sections : [];
  const fieldHeight = (field) => {
    if (field?.type === "paragraph" || field?.type === "file") return 118;
    if (["radio", "checkboxes"].includes(field?.type)) {
      return 82 + Math.max(1, Array.isArray(field.options) ? field.options.length : 0) * 38;
    }
    return 86;
  };
  const contentHeight = sections.reduce(
    (total, section) =>
      total + 72 + (section.fields || []).reduce((fieldTotal, field) => fieldTotal + fieldHeight(field), 0),
    0
  );
  const responsiveAllowance = viewportName === "mobile" ? 120 : viewportName === "tablet" ? 72 : 40;

  return Math.max(460, 190 + contentHeight + responsiveAllowance);
};

export const getMetricItems = (element) => {
  if (Array.isArray(element?.metrics) && element.metrics.length) return element.metrics;

  const lines = String(element?.content || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  const items = [];

  for (let index = 0; index < lines.length; index += 2) {
    items.push({
      label: lines[index] || `Metric ${items.length + 1}`,
      value: lines[index + 1] || "0",
    });
  }

  return items.length ? items : [{ label: "Metric", value: "0" }];
};

export const getSectionCanvasHeight = (section, viewportName) =>
  Number(section?.layout?.minHeightByViewport?.[viewportName]) ||
  Number(section?.layout?.minHeight) ||
  560;

export const commitDirectElementInteraction = (sections, {
  elementId,
  movedElement = null,
  previewPosition = null,
  previewSectionHeight = 0,
  sourceSectionId,
  targetSectionId = "",
  viewportName = "desktop",
} = {}) => {
  const isCrossSectionMove = Boolean(
    movedElement && targetSectionId && sourceSectionId !== targetSectionId
  );

  return sections.map((section) => {
    if (isCrossSectionMove && section.id === sourceSectionId) {
      return {
        ...section,
        freeElements: (section.freeElements || []).filter((element) => element.id !== elementId),
      };
    }

    if (isCrossSectionMove && section.id === targetSectionId) {
      const minHeightByViewport = { ...(section.layout?.minHeightByViewport || {}) };
      ["desktop", "tablet", "mobile"].forEach((nextViewportName) => {
        const position = movedElement.position?.[nextViewportName] || createPosition()[nextViewportName];
        minHeightByViewport[nextViewportName] = Math.max(
          getSectionCanvasHeight(section, nextViewportName),
          (Number(position.y) || 0) + (Number(position.height) || 0) + 48
        );
      });
      return {
        ...section,
        layout: {
          ...(section.layout || {}),
          minHeight: minHeightByViewport.desktop,
          minHeightByViewport,
        },
        freeElements: [...(section.freeElements || []), movedElement],
      };
    }

    if (isCrossSectionMove || section.id !== sourceSectionId || !previewPosition) return section;

    const currentHeight = getSectionCanvasHeight(section, viewportName);
    const nextHeight = Math.max(currentHeight, Number(previewSectionHeight) || 0);
    return {
      ...section,
      layout: {
        ...(section.layout || {}),
        minHeight: viewportName === "desktop" ? nextHeight : section.layout?.minHeight,
        minHeightByViewport: {
          ...(section.layout?.minHeightByViewport || {}),
          [viewportName]: nextHeight,
        },
      },
      freeElements: (section.freeElements || []).map((element) =>
        element.id === elementId
          ? {
              ...element,
              position: {
                ...(element.position || {}),
                [viewportName]: previewPosition,
              },
            }
          : element
      ),
    };
  });
};

export const getMinimumBuilderSectionHeight = (viewportHeight) => {
  const availableHeight = Math.max(0, Number(viewportHeight) || (typeof window !== "undefined" ? window.innerHeight : 900));
  return Math.max(360, Math.round((availableHeight - 126) * 0.5));
};

export const createDirectPositions = (section, viewportName) => {
  const canvasWidth = viewports[viewportName] || viewports.desktop;
  const maxColumns = viewportName === "mobile" ? 1 : viewportName === "tablet" ? 2 : 4;
  const gap = viewportName === "mobile" ? 14 : 20;
  const edge = viewportName === "mobile" ? 12 : 24;
  const positions = new Map();
  let rowY = edge;

  (section.rows || []).forEach((row) => {
    const sourceColumns = row.columns || [];
    const columnCount = Math.max(1, Math.min(sourceColumns.length || 1, maxColumns));
    const columnWidth = Math.floor(
      (canvasWidth - edge * 2 - gap * (columnCount - 1)) / columnCount
    );
    const columnBottoms = Array.from({ length: columnCount }, () => rowY);

    sourceColumns.forEach((column, sourceColumnIndex) => {
      const columnIndex = sourceColumnIndex % columnCount;
      if (sourceColumnIndex >= columnCount && columnIndex === 0) {
        const nextY = Math.max(...columnBottoms) + gap;
        columnBottoms.fill(nextY);
      }

      (column.elements || []).forEach((element) => {
        const height = directElementHeight(element);
        positions.set(element.id, {
          x: edge + columnIndex * (columnWidth + gap),
          y: columnBottoms[columnIndex],
          width: columnWidth,
          height,
        });
        columnBottoms[columnIndex] += height + gap;
      });
    });

    rowY = Math.max(rowY, ...columnBottoms) + gap;
  });

  return { positions, height: Math.max(240, rowY + edge) };
};

export const convertSectionToDirectLayout = (section) => {
  const shouldUseFullWidth = String(section?.name || "").toLowerCase().includes("login");
  const normalizedLayout = shouldUseFullWidth
    ? { ...(section.layout || {}), width: "full" }
    : section.layout;

  const normalizeDirectElements = (elements) =>
    (elements || []).map((element) => ({
      ...element,
      mode: "direct",
      position: shouldUseFullWidth || element.type === "metric"
        ? Object.fromEntries(
            ["desktop", "tablet", "mobile"].map((viewportName) => {
              const current = element.position?.[viewportName] || createPosition()[viewportName];
              const edge = viewportName === "mobile" ? 12 : 24;
              const metricHeight = viewportName === "desktop" ? 260 : viewportName === "tablet" ? 390 : 680;
              return [
                viewportName,
                {
                  ...current,
                  x: edge,
                  width: (viewports[viewportName] || viewports.desktop) - edge * 2,
                  ...(element.type === "metric"
                    ? { height: Math.max(Number(current.height) || 0, metricHeight) }
                    : {}),
                },
              ];
            })
          )
        : element.position,
    }));

  if (section.mode === "free") {
    return {
      ...section,
      layout: normalizedLayout,
      mode: "direct",
      freeElements: normalizeDirectElements(section.freeElements),
    };
  }

  if (section.mode === "direct") {
    return {
      ...section,
      layout: normalizedLayout,
      freeElements: normalizeDirectElements(section.freeElements),
    };
  }

  const elements = (section.rows || []).flatMap((row) =>
    (row.columns || []).flatMap((column) => column.elements || [])
  );

  const layouts = Object.fromEntries(
    ["desktop", "tablet", "mobile"].map((viewportName) => [
      viewportName,
      createDirectPositions(section, viewportName),
    ])
  );

  return {
    ...section,
    mode: "direct",
    layout: {
      ...normalizedLayout,
      minHeight: Math.max(Number(section.layout?.minHeight) || 0, layouts.desktop.height),
      minHeightByViewport: Object.fromEntries(
        Object.entries(layouts).map(([viewportName, layout]) => [
          viewportName,
          Math.max(Number(section.layout?.minHeight) || 0, layout.height),
        ])
      ),
    },
    rows: [],
    freeElements: elements.map((element) => ({
      ...element,
      mode: "direct",
      position: {
        ...(element.position || {}),
        desktop: layouts.desktop.positions.get(element.id) || createPosition().desktop,
        tablet: layouts.tablet.positions.get(element.id) || createPosition().tablet,
        mobile: layouts.mobile.positions.get(element.id) || createPosition().mobile,
      },
    })),
  };
};


export const mergeSectionsIntoPageCanvas = (page, sections) => {
  if (
    page.canvasLayoutVersion === 1 &&
    sections.length === 1 &&
    sections[0]?.isPageCanvas
  ) {
    return { ...page, sections };
  }

  const offsets = { desktop: 0, tablet: 0, mobile: 0 };
  const mergedElements = [];

  sections.forEach((section) => {
    (section.freeElements || []).forEach((element) => {
      const position = { ...(element.position || {}) };

      ["desktop", "tablet", "mobile"].forEach((viewportName) => {
        const current = element.position?.[viewportName] || createPosition()[viewportName];
        position[viewportName] = {
          ...current,
          y: (Number(current.y) || 0) + offsets[viewportName],
        };
      });

      mergedElements.push({
        ...element,
        mode: "direct",
        sourceSectionName: element.sourceSectionName || section.name || "Page",
        position,
      });
    });

    ["desktop", "tablet", "mobile"].forEach((viewportName) => {
      offsets[viewportName] += getSectionCanvasHeight(section, viewportName);
    });
  });

  const fallbackHeight = Math.max(720, ...Object.values(offsets));
  const firstSection = sections[0];
  const fallbackSectionId = `section_${String(page?.id || "page").replace(/[^a-z0-9]+/gi, "_").toLowerCase()}_canvas`;
  const canvasSection = {
    ...(firstSection || createSection({ id: fallbackSectionId, rows: [] })),
    id: firstSection?.id || fallbackSectionId,
    name: "Page Canvas",
    isPageCanvas: true,
    mode: "direct",
    rows: [],
    freeElements: mergedElements,
    layout: {
      ...(firstSection?.layout || {}),
      width: "full",
      paddingY: "none",
      background: "transparent",
      minHeight: offsets.desktop || fallbackHeight,
      minHeightByViewport: {
        desktop: offsets.desktop || fallbackHeight,
        tablet: offsets.tablet || fallbackHeight,
        mobile: offsets.mobile || fallbackHeight,
      },
    },
  };

  return {
    ...page,
    canvasLayoutVersion: 1,
    sections: [canvasSection],
  };
};




export const positionsOverlap = (candidate, other, spacing = 8) =>
  candidate.x < other.x + other.width + spacing &&
  candidate.x + candidate.width + spacing > other.x &&
  candidate.y < other.y + other.height + spacing &&
  candidate.y + candidate.height + spacing > other.y;

export const getProjectOverlapWarnings = ({
  project,
  createPosition,
  positionsOverlap,
}) => {
  const warnings = [];

  (project.pages || []).forEach((page) => {
    (page.sections || []).forEach((section) => {
      const elements = section.freeElements || [];

      ["desktop", "tablet", "mobile"].forEach((viewportName) => {
        elements.forEach((element, elementIndex) => {
          const elementPosition = element.position?.[viewportName] || createPosition()[viewportName];

          elements.slice(elementIndex + 1).forEach((other) => {
            const otherPosition = other.position?.[viewportName] || createPosition()[viewportName];

            if (positionsOverlap(elementPosition, otherPosition, 0)) {
              warnings.push({
                page: page.name || "Untitled page",
                section: section.name || "Untitled section",
                viewport: viewportName,
                first: element.name || element.type || "Component",
                second: other.name || other.type || "Component",
              });
            }
          });
        });
      });
    });
  });

  return warnings;
};

export const snapToGrid = (value, gridSize = 8) => Math.round(value / gridSize) * gridSize;

export const getDragCandidatePosition = ({
  dragState,
  selectedElement,
  canvasWidth,
  canvasHeight,
  bounds = {
    x: 0,
    y: 0,
    width: canvasWidth,
    height: canvasHeight,
  },
  allowBottomOverflow = false,
  snapToGrid,
}) => {
  const minimumSize = getDirectElementMinimumSize(selectedElement);
  const roundPixel = (value) => Math.round(Number(value) || 0);
  const resizing = dragState.interaction === "resize";
  const resizeSensitivity = selectedElement?.type === "heading" ? 0.45 : 1;
  const candidate = resizing
    ? {
        x: dragState.startX,
        y: dragState.startY,
        width: roundPixel(dragState.startWidth + dragState.deltaX * resizeSensitivity),
        height: roundPixel(dragState.startHeight + dragState.deltaY * resizeSensitivity),
      }
    : {
        x: snapToGrid(dragState.startX + dragState.deltaX),
        y: snapToGrid(dragState.startY + dragState.deltaY),
        width: dragState.startWidth,
        height: dragState.startHeight,
      };

  return clampElementToBounds(candidate, bounds, {
    minWidth: minimumSize.width,
    minHeight: minimumSize.height,
    mode: resizing ? "resize" : "move",
    allowBottomOverflow,
  });
};

export const getMovedElementPosition = ({
  selectedElement,
  targetSection,
  viewport,
  event,
  frameRect,
  canvasScale = 1,
  activeBounds = null,
  activePoint = null,
  viewports,
  createPosition,
  getSectionCanvasHeight,
}) => {
  const nextPosition = { ...(selectedElement.position || {}) };

  ["desktop", "tablet", "mobile"].forEach((viewportName) => {
    const current = selectedElement.position?.[viewportName] || createPosition()[viewportName];
    const canvasWidth = viewports[viewportName] || viewports.desktop;
    const canvasHeight = getSectionCanvasHeight(targetSection, viewportName);
    const width = Math.min(Number(current.width) || 240, canvasWidth);
    const height = Number(current.height) || 80;

    nextPosition[viewportName] = clampElementToBounds(
      { ...current, width, height },
      { x: 0, y: 0, width: canvasWidth, height: canvasHeight },
      {
        minWidth: getDirectElementMinimumSize(selectedElement).width,
        minHeight: getDirectElementMinimumSize(selectedElement).height,
        allowBottomOverflow: true,
      }
    );
  });

  const activePosition = nextPosition[viewport];
  const pointer = activePoint || {
    x: (event.clientX - frameRect.left) / canvasScale,
    y: (event.clientY - frameRect.top) / canvasScale,
  };
  nextPosition[viewport] = clampElementToBounds(
    {
      ...activePosition,
      x: Math.round(pointer.x - activePosition.width / 2),
      y: Math.round(pointer.y - activePosition.height / 2),
    },
    activeBounds || {
      x: 0,
      y: 0,
      width: viewports[viewport] || viewports.desktop,
      height: getSectionCanvasHeight(targetSection, viewport),
    },
    {
      minWidth: getDirectElementMinimumSize(selectedElement).width,
      minHeight: getDirectElementMinimumSize(selectedElement).height,
      allowBottomOverflow: true,
    }
  );

  return nextPosition;
};

export const moveFreeElementBetweenSections = ({
  sections,
  sourceSectionId,
  targetSectionId,
  elementId,
  movedElement,
}) =>
  sections.map((section) => {
    if (section.id === sourceSectionId) {
      return {
        ...section,
        freeElements: (section.freeElements || []).filter((element) => element.id !== elementId),
      };
    }

    if (section.id === targetSectionId) {
      return {
        ...section,
        freeElements: [...(section.freeElements || []), movedElement],
      };
    }

    return section;
  });

export const createMovedFreeElement = (element, position) => ({
  ...element,
  position,
});
