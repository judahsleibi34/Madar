const finite = (value, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const round = (value) => Math.round(finite(value) * 1000) / 1000;

const TABLET_FLUID_TYPES = new Set([
  "heading",
  "text",
  "list",
  "divider",
  "thinDivider",
  "card",
  "carousel",
  "carouselCards",
  "carouselSplit",
  "carouselSpotlight",
  "carouselStack",
  "carouselEditorial",
  "circularGallery",
  "photoProofing",
  "document",
  "formBlock",
  "reservationBlock",
  "loginBlock",
  "registrationBlock",
]);

const TABLET_MEDIA_TYPES = new Set(["image", "imageButton", "video", "embed"]);

const getResponsiveButtonPosition = (node, source, bounds) => {
  const alignment = node.element?.styles?.alignSelf;
  const normalizedAlignment = alignment === "left"
    ? "flex-start"
    : alignment === "right"
      ? "flex-end"
      : alignment;

  if (normalizedAlignment === "stretch") {
    return { ...source, x: bounds.x, width: bounds.width };
  }

  const targetWidth = Math.min(bounds.width, source.width);
  let x = bounds.x + (bounds.width - targetWidth) / 2;
  if (normalizedAlignment === "flex-start") x = bounds.x;
  if (normalizedAlignment === "flex-end") {
    x = bounds.x + bounds.width - targetWidth;
  }

  return { ...source, x: round(x), width: round(targetWidth) };
};

const normalizeEntry = (entry) => ({
  ...entry,
  position: {
    ...entry.position,
    x: finite(entry.position?.x),
    y: finite(entry.position?.y),
    width: Math.max(1, finite(entry.position?.width, 240)),
    height: Math.max(1, finite(entry.position?.height, 80)),
  },
});

const overlapLength = (startA, sizeA, startB, sizeB) =>
  Math.max(0, Math.min(startA + sizeA, startB + sizeB) - Math.max(startA, startB));

const sharesAuthoredRow = (first, second) => {
  const verticalOverlap = overlapLength(
    first.position.y,
    first.position.height,
    second.position.y,
    second.position.height
  );
  const verticalRatio = verticalOverlap / Math.max(
    1,
    Math.min(first.position.height, second.position.height)
  );
  const firstRight = first.position.x + first.position.width;
  const secondRight = second.position.x + second.position.width;
  const horizontallySeparate = firstRight <= second.position.x || secondRight <= first.position.x;
  return verticalRatio >= 0.35 && horizontallySeparate;
};

export const getTabletContentBounds = (artboardWidth) => {
  const width = Math.max(1, finite(artboardWidth, 768));
  const inset = Math.ceil(Math.max(28, width * 0.05));
  return { x: inset, width: Math.max(1, width - inset * 2) };
};

export const getMobileContentBounds = (artboardWidth) => {
  const width = Math.max(1, finite(artboardWidth, 390));
  const inset = Math.ceil(Math.max(20, width * 0.06));
  return { x: inset, width: Math.max(1, width - inset * 2) };
};

/**
 * Produces readable tablet widths without mutating saved breakpoint geometry.
 * Authored multi-column rows scale as a group; single flow components fill the
 * content lane; visual media keeps its aspect ratio and is centered.
 */
export const resolveResponsiveElementSizing = (
  entries = [],
  viewportMode = "desktop",
  artboardWidth = 1200
) => {
  const nodes = entries.map(normalizeEntry);
  if (viewportMode === "mobile") {
    const width = Math.max(1, finite(artboardWidth, 390));
    const bounds = getMobileContentBounds(width);
    const horizontalScale = bounds.width / width;
    const rowMemberIds = new Set();
    nodes.forEach((node, index) => {
      if (nodes.some((other, otherIndex) => otherIndex !== index && sharesAuthoredRow(node, other))) {
        rowMemberIds.add(node.element.id);
      }
    });

    return nodes.map((node) => {
      const source = node.position;
      if (node.flowRole === "underText" || node.element?.layer === "behindText") return node;

      if (rowMemberIds.has(node.element.id)) {
        return {
          ...node,
          position: {
            ...source,
            x: round(bounds.x + source.x * horizontalScale),
            width: round(Math.min(bounds.width, source.width * horizontalScale)),
          },
        };
      }

      if (
        node.element?.type === "imageButton" &&
        node.element.imageButtonVariant === "editorialCard"
      ) {
        return {
          ...node,
          position: { ...source, x: bounds.x, width: bounds.width, height: 240 },
        };
      }

      if (TABLET_MEDIA_TYPES.has(node.element?.type)) {
        const targetWidth = bounds.width;
        const scale = targetWidth / source.width;
        return {
          ...node,
          position: {
            ...source,
            x: bounds.x,
            width: targetWidth,
            height: round(source.height * scale),
          },
        };
      }

      if (TABLET_FLUID_TYPES.has(node.element?.type)) {
        return {
          ...node,
          position: { ...source, x: bounds.x, width: bounds.width },
        };
      }

      if (node.element?.type === "button") {
        return {
          ...node,
          position: getResponsiveButtonPosition(node, source, bounds),
        };
      }

      const targetWidth = Math.min(bounds.width, source.width);
      return {
        ...node,
        position: {
          ...source,
          x: round(Math.min(
            Math.max(bounds.x, source.x),
            bounds.x + bounds.width - targetWidth
          )),
          width: targetWidth,
        },
      };
    });
  }
  if (viewportMode !== "tablet") return nodes;

  const width = Math.max(1, finite(artboardWidth, 768));
  const bounds = getTabletContentBounds(width);
  const horizontalScale = bounds.width / width;
  const rowMemberIds = new Set();

  nodes.forEach((node, index) => {
    if (nodes.some((other, otherIndex) => otherIndex !== index && sharesAuthoredRow(node, other))) {
      rowMemberIds.add(node.element.id);
    }
  });

  return nodes.map((node) => {
    const source = node.position;
    if (node.flowRole === "underText" || node.element?.layer === "behindText") return node;

    if (rowMemberIds.has(node.element.id)) {
      return {
        ...node,
        position: {
          ...source,
          x: round(bounds.x + source.x * horizontalScale),
          width: round(Math.min(bounds.width, source.width * horizontalScale)),
        },
      };
    }

    if (TABLET_MEDIA_TYPES.has(node.element?.type)) {
      const targetWidth = Math.min(
        bounds.width,
        Math.max(source.width, bounds.width * 0.62)
      );
      const scale = targetWidth / source.width;
      return {
        ...node,
        position: {
          ...source,
          x: round((width - targetWidth) / 2),
          width: round(targetWidth),
          height: round(source.height * scale),
        },
      };
    }

    if (TABLET_FLUID_TYPES.has(node.element?.type)) {
      return {
        ...node,
        position: { ...source, x: bounds.x, width: bounds.width },
      };
    }


    if (node.element?.type === "button") {
      return {
        ...node,
        position: getResponsiveButtonPosition(node, source, bounds),
      };
    }

    const targetWidth = Math.min(bounds.width, Math.max(source.width, bounds.width * 0.72));
    return {
      ...node,
      position: { ...source, x: bounds.x, width: round(targetWidth) },
    };
  });
};
