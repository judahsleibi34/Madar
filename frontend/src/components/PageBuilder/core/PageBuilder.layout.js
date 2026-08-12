import { MAX_BUILDER_IMAGE_WIDTH_PX, viewports } from "./PageBuilder.constants";
import { createPosition, createSection } from "./PageBuilder.factories";
import { clampElementToBounds } from "./PageBuilder.bounds";
import { withManualResponsiveOverride } from "./PageBuilder.responsiveCapabilities";

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
    return { width: 320, height: 320 };
  }

  if (element?.type === "button") {
    return { width: 80, height: 42 };
  }

  if (["divider", "thinDivider"].includes(element?.type)) {
    return { width: 80, height: 24 };
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
    imageButton: 180,
    image: 260,
    video: 320,
    document: 150,
    photoProofing: 330,
    card: 390,
    list: 170,
    divider: 32,
    thinDivider: 32,
    formBlock: 460,
    reservationBlock: 770,
    loginBlock: 390,
    registrationBlock: 520,
    carousel: 420,
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

export const getSectionCanvasHeight = (section, viewportName) => {
  if (["direct", "free"].includes(section?.mode)) {
    const positionedElements = (section?.freeElements || []).filter(
      (element) => element.position?.[viewportName]
    );
    if ((section?.freeElements || []).length === 0) return 120;
    if (positionedElements.length > 0) {
      return positionedElements.reduce((requiredHeight, element) => {
        const position = element.position[viewportName];
        return Math.max(
          requiredHeight,
          (Number(position.y) || 0) + (Number(position.height) || 0) + 48
        );
      }, 120);
    }
  }

  return Number(section?.layout?.minHeightByViewport?.[viewportName]) ||
    Number(section?.layout?.minHeight) ||
    560;
};

const horizontalRangesOverlap = (first = {}, second = {}) => {
  const firstLeft = Number(first.x) || 0;
  const secondLeft = Number(second.x) || 0;
  const firstRight = firstLeft + (Number(first.width) || 0);
  const secondRight = secondLeft + (Number(second.width) || 0);
  return firstLeft < secondRight && firstRight > secondLeft;
};

export const compactDirectSectionAfterElementRemoval = (
  section,
  elementId,
  { minimumHeight = 120, verticalGap = 16, bottomPadding = 48 } = {}
) => {
  const sourceElements = section?.freeElements || [];
  const removedElement = sourceElements.find((element) => element.id === elementId);
  if (!removedElement) return section;

  const remainingElements = sourceElements.filter((element) => element.id !== elementId);
  const minHeightByViewport = {};
  const compactedElements = remainingElements.map((element) => ({
    ...element,
    position: { ...(element.position || {}) },
  }));

  ["desktop", "tablet", "mobile"].forEach((viewportName) => {
    const removedPosition = removedElement.position?.[viewportName];
    const removedBottom = removedPosition
      ? (Number(removedPosition.y) || 0) + (Number(removedPosition.height) || 0)
      : 0;
    const reclaimedHeight = removedPosition
      ? (Number(removedPosition.height) || 0) + verticalGap
      : 0;

    compactedElements.forEach((element) => {
      const position = element.position?.[viewportName];
      if (!position || !removedPosition) return;
      const isBelowRemoved = (Number(position.y) || 0) >= removedBottom - 1;
      if (!isBelowRemoved || !horizontalRangesOverlap(position, removedPosition)) return;

      element.position[viewportName] = {
        ...position,
        y: Math.max(8, (Number(position.y) || 0) - reclaimedHeight),
      };
    });

    minHeightByViewport[viewportName] = compactedElements.reduce((requiredHeight, element) => {
      const position = element.position?.[viewportName];
      if (!position) return requiredHeight;
      return Math.max(
        requiredHeight,
        (Number(position.y) || 0) + (Number(position.height) || 0) + bottomPadding
      );
    }, minimumHeight);
  });

  return {
    ...section,
    layout: {
      ...(section.layout || {}),
      minHeight: minHeightByViewport.desktop,
      minHeightByViewport,
    },
    freeElements: compactedElements,
  };
};

export const commitDirectElementInteraction = (sections, {
  elementId,
  movedElement = null,
  previewPosition = null,
  previewSectionHeight = 0,
  sourceSectionId,
  targetSectionId = "",
  viewportName = "desktop",
  elementUpdates = null,
  smartResponsive = false,
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
        freeElements: [
          ...(section.freeElements || []),
          smartResponsive
            ? withManualResponsiveOverride(
                movedElement,
                viewportName,
                movedElement.position?.[viewportName] || createPosition()[viewportName]
              )
            : movedElement,
        ],
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
      freeElements: (section.freeElements || []).map((element) => {
        if (element.id !== elementId) return element;
        const updatedElement = {
              ...element,
              ...(elementUpdates || {}),
              position: {
                ...(element.position || {}),
                [viewportName]: previewPosition,
              },
            };
        return smartResponsive
          ? withManualResponsiveOverride(updatedElement, viewportName, previewPosition)
          : updatedElement;
      }),
    };
  });
};

export const getMarqueeSelectionIds = (elements = [], viewportName = "desktop", rectangle = {}) => {
  const left = Math.min(Number(rectangle.startX) || 0, Number(rectangle.currentX) || 0);
  const top = Math.min(Number(rectangle.startY) || 0, Number(rectangle.currentY) || 0);
  const right = Math.max(Number(rectangle.startX) || 0, Number(rectangle.currentX) || 0);
  const bottom = Math.max(Number(rectangle.startY) || 0, Number(rectangle.currentY) || 0);

  return elements.filter((element) => {
    const position = element.position?.[viewportName];
    if (!position) return false;
    const elementLeft = Number(position.x) || 0;
    const elementTop = Number(position.y) || 0;
    const elementRight = elementLeft + (Number(position.width) || 0);
    const elementBottom = elementTop + (Number(position.height) || 0);
    return elementRight >= left && elementLeft <= right && elementBottom >= top && elementTop <= bottom;
  }).map((element) => element.id);
};

export const getSmartGuideSnap = ({
  candidate,
  siblings = [],
  canvasWidth = 0,
  canvasHeight = 0,
  canvasBounds = null,
  interaction = "move",
  threshold = 6,
  spacing = 12,
} = {}) => {
  if (!candidate) return { position: candidate, guides: [] };

  const position = {
    ...candidate,
    x: Number(candidate.x) || 0,
    y: Number(candidate.y) || 0,
    width: Number(candidate.width) || 0,
    height: Number(candidate.height) || 0,
  };
  const normalizedSiblings = siblings
    .map((item) => item?.position || item)
    .filter(Boolean)
    .map((item) => ({
      x: Number(item.x) || 0,
      y: Number(item.y) || 0,
      width: Number(item.width) || 0,
      height: Number(item.height) || 0,
    }));
  const choose = (options) => options
    .filter((option) => Math.abs(option.delta) <= threshold)
    .sort((first, second) => Math.abs(first.delta) - Math.abs(second.delta) ||
      (second.priority || 0) - (first.priority || 0))[0];
  const xOptions = [];
  const yOptions = [];
  const visibleCanvas = canvasBounds || { x: 0, y: 0, width: canvasWidth, height: canvasHeight };
  const canvasCenterX = (Number(visibleCanvas.x) || 0) + (Number(visibleCanvas.width) || 0) / 2;
  const canvasCenterY = (Number(visibleCanvas.y) || 0) + (Number(visibleCanvas.height) || 0) / 2;
  const candidateCenterX = position.x + position.width / 2;
  const candidateCenterY = position.y + position.height / 2;
  const candidateRight = position.x + position.width;
  const candidateBottom = position.y + position.height;
  const alignmentGuide = (axis, value, sibling, kind = "alignment") => ({
    axis,
    value,
    start: axis === "vertical"
      ? Math.min(position.y, sibling?.y ?? visibleCanvas.y)
      : Math.min(position.x, sibling?.x ?? visibleCanvas.x),
    end: axis === "vertical"
      ? Math.max(position.y + position.height, sibling ? sibling.y + sibling.height : visibleCanvas.y + visibleCanvas.height)
      : Math.max(position.x + position.width, sibling ? sibling.x + sibling.width : visibleCanvas.x + visibleCanvas.width),
    kind,
  });

  if (interaction === "move") {
    xOptions.push({
      delta: canvasCenterX - candidateCenterX,
      priority: 3,
      guides: [alignmentGuide("vertical", canvasCenterX, null, "canvas-center")],
    });
    yOptions.push({
      delta: canvasCenterY - candidateCenterY,
      priority: 3,
      guides: [alignmentGuide("horizontal", canvasCenterY, null, "canvas-center")],
    });
  } else {
    xOptions.push({
      delta: canvasCenterX - candidateRight,
      priority: 3,
      guides: [alignmentGuide("vertical", canvasCenterX, null, "canvas-center")],
    });
    yOptions.push({
      delta: canvasCenterY - candidateBottom,
      priority: 3,
      guides: [alignmentGuide("horizontal", canvasCenterY, null, "canvas-center")],
    });
  }

  normalizedSiblings.forEach((sibling) => {
    const siblingRight = sibling.x + sibling.width;
    const siblingBottom = sibling.y + sibling.height;
    const siblingCenterX = sibling.x + sibling.width / 2;
    const siblingCenterY = sibling.y + sibling.height / 2;
    const xPairs = interaction === "move"
      ? [[position.x, sibling.x], [candidateCenterX, siblingCenterX], [candidateRight, siblingRight]]
      : [[candidateRight, sibling.x - spacing], [candidateRight, siblingCenterX], [candidateRight, siblingRight]];
    const yPairs = interaction === "move"
      ? [[position.y, sibling.y], [candidateCenterY, siblingCenterY], [candidateBottom, siblingBottom]]
      : [[candidateBottom, sibling.y - spacing], [candidateBottom, siblingCenterY], [candidateBottom, siblingBottom]];

    xPairs.forEach(([source, target]) => xOptions.push({
      delta: target - source,
      priority: 1,
      guides: [alignmentGuide("vertical", target, sibling)],
    }));
    yPairs.forEach(([source, target]) => yOptions.push({
      delta: target - source,
      priority: 1,
      guides: [alignmentGuide("horizontal", target, sibling)],
    }));
  });

  if (interaction === "move") {
    const left = normalizedSiblings
      .filter((sibling) => sibling.x + sibling.width <= position.x)
      .sort((first, second) => second.x + second.width - (first.x + first.width))[0];
    const right = normalizedSiblings
      .filter((sibling) => sibling.x >= candidateRight)
      .sort((first, second) => first.x - second.x)[0];
    if (left && right) {
      const leftEdge = left.x + left.width;
      const desiredX = (leftEdge + right.x - position.width) / 2;
      const gap = Math.round(desiredX - leftEdge);
      xOptions.push({
        delta: desiredX - position.x,
        priority: 4,
        guides: [
          { axis: "horizontal", value: candidateCenterY, start: leftEdge, end: desiredX, kind: "spacing", label: `${gap}px` },
          { axis: "horizontal", value: candidateCenterY, start: desiredX + position.width, end: right.x, kind: "spacing", label: `${gap}px` },
        ],
      });
    }

    const above = normalizedSiblings
      .filter((sibling) => sibling.y + sibling.height <= position.y)
      .sort((first, second) => second.y + second.height - (first.y + first.height))[0];
    const below = normalizedSiblings
      .filter((sibling) => sibling.y >= candidateBottom)
      .sort((first, second) => first.y - second.y)[0];
    if (above && below) {
      const aboveEdge = above.y + above.height;
      const desiredY = (aboveEdge + below.y - position.height) / 2;
      const gap = Math.round(desiredY - aboveEdge);
      yOptions.push({
        delta: desiredY - position.y,
        priority: 4,
        guides: [
          { axis: "vertical", value: candidateCenterX, start: aboveEdge, end: desiredY, kind: "spacing", label: `${gap}px` },
          { axis: "vertical", value: candidateCenterX, start: desiredY + position.height, end: below.y, kind: "spacing", label: `${gap}px` },
        ],
      });
    }
  }

  const xSnap = choose(xOptions);
  const ySnap = choose(yOptions);
  if (interaction === "resize") {
    if (xSnap) position.width += xSnap.delta;
    if (ySnap) position.height += ySnap.delta;
  } else {
    if (xSnap) position.x += xSnap.delta;
    if (ySnap) position.y += ySnap.delta;
  }

  return {
    position: {
      ...position,
      x: Math.round(position.x),
      y: Math.round(position.y),
      width: Math.round(position.width),
      height: Math.round(position.height),
    },
    guides: [
      ...(xSnap?.guides || []).map((guide) => ({ ...guide, dimension: "x" })),
      ...(ySnap?.guides || []).map((guide) => ({ ...guide, dimension: "y" })),
    ],
  };
};
export const getPositionCollectionBounds = (positions = {}) => {
  const values = (Array.isArray(positions) ? positions : Object.values(positions))
    .filter(Boolean);
  if (!values.length) return null;
  const x = Math.min(...values.map((position) => Number(position.x) || 0));
  const y = Math.min(...values.map((position) => Number(position.y) || 0));
  const right = Math.max(...values.map((position) =>
    (Number(position.x) || 0) + (Number(position.width) || 0)
  ));
  const bottom = Math.max(...values.map((position) =>
    (Number(position.y) || 0) + (Number(position.height) || 0)
  ));
  return { x, y, width: right - x, height: bottom - y };
};
export const getGroupDragPreviewPositions = ({
  startPositions = {},
  primaryElementId,
  primaryPreview,
  bounds = { x: 0, y: 0, width: 0, height: 0 },
} = {}) => {
  const entries = Object.entries(startPositions).filter(([, position]) => position);
  const primaryStart = startPositions[primaryElementId];
  if (!entries.length || !primaryStart || !primaryPreview) return {};

  const minX = Math.min(...entries.map(([, position]) => Number(position.x) || 0));
  const minY = Math.min(...entries.map(([, position]) => Number(position.y) || 0));
  const maxRight = Math.max(...entries.map(([, position]) =>
    (Number(position.x) || 0) + (Number(position.width) || 0)
  ));
  const desiredX = (Number(primaryPreview.x) || 0) - (Number(primaryStart.x) || 0);
  const desiredY = (Number(primaryPreview.y) || 0) - (Number(primaryStart.y) || 0);
  const minimumDeltaX = (Number(bounds.x) || 0) - minX;
  const maximumDeltaX = (Number(bounds.x) || 0) + (Number(bounds.width) || 0) - maxRight;
  const minimumDeltaY = (Number(bounds.y) || 0) - minY;
  const deltaX = Math.min(Math.max(desiredX, minimumDeltaX), maximumDeltaX);
  const deltaY = Math.max(desiredY, minimumDeltaY);

  return Object.fromEntries(entries.map(([elementId, position]) => [elementId, {
    ...position,
    x: Math.round((Number(position.x) || 0) + deltaX),
    y: Math.round((Number(position.y) || 0) + deltaY),
  }]));
};

export const commitDirectElementGroupInteraction = (sections, {
  sourceSectionId,
  previewPositions = {},
  previewSectionHeight = 0,
  viewportName = "desktop",
  smartResponsive = false,
} = {}) => sections.map((section) => {
  if (section.id !== sourceSectionId || !Object.keys(previewPositions).length) return section;

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
    freeElements: (section.freeElements || []).map((element) => {
      if (!previewPositions[element.id]) return element;
      const updatedElement = {
            ...element,
            position: {
              ...(element.position || {}),
              [viewportName]: previewPositions[element.id],
            },
          };
      return smartResponsive
        ? withManualResponsiveOverride(updatedElement, viewportName, previewPositions[element.id])
        : updatedElement;
    }),
  };
});

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

const textLayerElementTypes = new Set(["heading", "text", "list"]);

export const moveElementBehindText = (elements = [], elementId = "") => {
  const elementIndex = elements.findIndex((element) => element.id === elementId);
  if (elementIndex < 0) return elements;

  const element = elements[elementIndex];
  const layeredElement = element.layer === "behindText"
    ? element
    : { ...element, layer: "behindText" };
  const remainingElements = elements.filter((item) => item.id !== elementId);
  const firstTextIndex = remainingElements.findIndex((item) =>
    textLayerElementTypes.has(item.type)
  );

  if (firstTextIndex < 0) return elements;

  const reorderedElements = [...remainingElements];
  reorderedElements.splice(firstTextIndex, 0, layeredElement);
  if (reorderedElements.every((item, index) => item === elements[index])) return elements;
  return reorderedElements;
};

export const moveElementToFront = (elements = [], elementId = "") => {
  const elementIndex = elements.findIndex((element) => element.id === elementId);
  if (elementIndex < 0) return elements;

  const frontElement = { ...elements[elementIndex], layer: undefined };
  const reorderedElements = [
    ...elements.filter((element) => element.id !== elementId),
    frontElement,
  ];
  if (reorderedElements.every((element, index) => element === elements[index])) return elements;
  return reorderedElements;
};

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
  const resizingImage = resizing && selectedElement?.type === "image";
  const storedImageAspectRatio = Number(selectedElement?.mediaAspectRatio);
  const currentImageAspectRatio = Number(dragState.startWidth) / Number(dragState.startHeight);
  const imageAspectRatio = storedImageAspectRatio > 0
    ? storedImageAspectRatio
    : currentImageAspectRatio > 0
      ? currentImageAspectRatio
      : 1;
  const requestedWidth = roundPixel(dragState.startWidth + dragState.deltaX);
  const requestedHeight = roundPixel(dragState.startHeight + dragState.deltaY);
  const horizontalResizeChange = Math.abs(
    (Number(dragState.deltaX) || 0) / Math.max(1, Number(dragState.startWidth) || 1)
  );
  const verticalResizeChange = Math.abs(
    (Number(dragState.deltaY) || 0) / Math.max(1, Number(dragState.startHeight) || 1)
  );
  const resizeImageFromHeight = resizingImage && verticalResizeChange > horizontalResizeChange;
  const unconstrainedImageWidth = resizeImageFromHeight
    ? requestedHeight * imageAspectRatio
    : requestedWidth;
  const availableImageWidth = Math.max(0, bounds.x + bounds.width - dragState.startX);
  const availableImageHeight = allowBottomOverflow
    ? Number.POSITIVE_INFINITY
    : Math.max(0, bounds.y + bounds.height - dragState.startY);
  const maximumImageWidth = Math.min(
    MAX_BUILDER_IMAGE_WIDTH_PX,
    availableImageWidth,
    availableImageHeight * imageAspectRatio
  );
  const minimumAspectLockedImageWidth = Math.min(
    maximumImageWidth,
    Math.max(minimumSize.width, minimumSize.height * imageAspectRatio)
  );
  const imageWidth = resizingImage
    ? roundPixel(Math.max(
        minimumAspectLockedImageWidth,
        Math.min(unconstrainedImageWidth, maximumImageWidth)
      ))
    : requestedWidth;
  const candidate = resizing
    ? {
        x: dragState.startX,
        y: dragState.startY,
        width: imageWidth,
        height: resizingImage
          ? roundPixel(imageWidth / imageAspectRatio)
          : requestedHeight,
      }
    : {
        x: snapToGrid(dragState.startX + dragState.deltaX),
        y: snapToGrid(dragState.startY + dragState.deltaY),
        width: dragState.startWidth,
        height: dragState.startHeight,
      };

  return clampElementToBounds(candidate, bounds, {
    minWidth: minimumSize.width,
    maxWidth: resizingImage ? MAX_BUILDER_IMAGE_WIDTH_PX : undefined,
    minHeight: minimumSize.height,
    mode: resizing ? "resize" : "move",
    allowBottomOverflow,
  });
};

export const constrainResizeToSiblingElements = ({
  candidate,
  siblings = [],
  selectedElement,
  viewport,
  createPosition,
  dragState,
  canvasWidth,
  spacing = 12,
}) => {
  if (selectedElement?.type === "image" || selectedElement?.layer === "behindText") {
    return candidate;
  }

  return siblings.reduce((nextCandidate, element) => {
    const other = element.position?.[viewport] || createPosition()[viewport];
    if (!positionsOverlap(nextCandidate, other, spacing)) return nextCandidate;

    const minimumSize = getDirectElementMinimumSize(selectedElement);
    const clamped = { ...nextCandidate };
    const verticalRangesMeet = nextCandidate.y < other.y + other.height + spacing &&
      nextCandidate.y + nextCandidate.height + spacing > other.y;
    const horizontalRangesMeet = nextCandidate.x < other.x + other.width + spacing &&
      nextCandidate.x + nextCandidate.width + spacing > other.x;

    if (other.x >= dragState.startX + dragState.startWidth + spacing && verticalRangesMeet) {
      clamped.width = Math.max(
        Math.min(minimumSize.width, canvasWidth - nextCandidate.x),
        Math.round(other.x - nextCandidate.x - spacing)
      );
    }
    if (other.y >= nextCandidate.y && horizontalRangesMeet) {
      clamped.height = Math.max(minimumSize.height, Math.round(other.y - nextCandidate.y - spacing));
    }
    return clamped;
  }, candidate);
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
