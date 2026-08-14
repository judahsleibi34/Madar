const finite = (value, fallback = 0) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const normalizePosition = (position = {}) => ({
  ...position,
  x: finite(position.x),
  y: finite(position.y),
  width: Math.max(1, finite(position.width, 240)),
  height: Math.max(1, finite(position.height, 80)),
});

const UNDER_TEXT_CONTENT_TYPES = new Set(["heading", "text", "list"]);
const COMPACT_SEPARATOR_TYPES = new Set(["divider", "thinDivider"]);

const getCollisionPadding = (element, precedingHeight, paddingRatio) =>
  COMPACT_SEPARATOR_TYPES.has(element?.type)
    ? 0
    : Math.ceil(precedingHeight * paddingRatio);

const horizontalRangesOverlap = (first, second) =>
  first.x < second.x + second.width && first.x + first.width > second.x;

const compareInReadingOrder = (first, second) =>
  (first.position.y - second.position.y) ||
  (first.position.x - second.position.x) ||
  (first.sourceIndex - second.sourceIndex) ||
  String(first.element.id).localeCompare(String(second.element.id));

/**
 * Derives non-overlapping positions without changing saved breakpoint geometry.
 * Elements are processed in stable visual order. A later foreground element is
 * moved only on the y axis when its horizontal lane intersects an earlier one.
 */
export const RESPONSIVE_ELEMENT_GAP_RATIO = 0.15;

/**
 * Repairs contradictory phone geometry using the desktop visual reading order.
 * Under-text artwork is inserted after the first desktop text alongside it.
 * This creates the expected left-to-right hero sequence on phones even when
 * legacy storage placed the image earlier in the raw component array.
 */
export const resolveMobileReadingOrder = (
  entries = [],
  gapRatio = RESPONSIVE_ELEMENT_GAP_RATIO
) => {
  const nodes = entries.map((entry, sourceIndex) => ({
    ...entry,
    sourceIndex,
    position: normalizePosition(entry.position),
    readingOrderPosition: normalizePosition(entry.readingOrderPosition || entry.position),
  }));
  const foreground = nodes.filter(
    (node) => node.flowRole !== 'underText' && node.element?.layer !== 'behindText'
  );
  const foregroundReadingOrder = [...foreground].sort((first, second) =>
    (first.readingOrderPosition.y - second.readingOrderPosition.y) ||
    (first.readingOrderPosition.x - second.readingOrderPosition.x) ||
    (first.sourceIndex - second.sourceIndex)
  );
  const readingOrder = nodes
    .filter((node) =>
      node.flowRole === 'underText'
      || (node.element?.type === 'image' && node.element?.layer === 'behindText')
    )
    .sort((first, second) => first.sourceIndex - second.sourceIndex)
    .reduce((order, artwork) => {
      const artworkPosition = artwork.readingOrderPosition;
      const artworkBottom = artworkPosition.y + artworkPosition.height;
      const leftTextAnchor = order
        .filter((node) => {
          const position = node.readingOrderPosition;
          return position.y >= artworkPosition.y
            && position.y < artworkBottom
            && position.x < artworkPosition.x + artworkPosition.width;
        })
        .sort((first, second) =>
          (first.readingOrderPosition.x - second.readingOrderPosition.x)
          || (first.readingOrderPosition.y - second.readingOrderPosition.y)
          || (first.sourceIndex - second.sourceIndex)
        )[0];
      const leftTextIndex = leftTextAnchor ? order.indexOf(leftTextAnchor) : -1;
      const nextEncodedElementIndex = order.findIndex(
        (node) => node.sourceIndex > artwork.sourceIndex
      );
      const insertionIndex = leftTextIndex >= 0
        ? leftTextIndex + 1
        : nextEncodedElementIndex < 0
          ? order.length
          : nextEncodedElementIndex;
      order.splice(insertionIndex, 0, artwork);
      return order;
    }, foregroundReadingOrder);
  if (readingOrder.length < 2) return nodes;

  const paddingRatio = Math.max(0, finite(gapRatio, RESPONSIVE_ELEMENT_GAP_RATIO));
  let nextY = Math.min(...readingOrder.map((node) => node.position.y));
  const repairedYById = new Map();

  readingOrder.forEach((node) => {
    repairedYById.set(node.element.id, nextY);
    nextY += node.position.height + Math.ceil(node.position.height * paddingRatio);
  });

  return nodes.map((node) => {
    const repairedY = repairedYById.get(node.element.id);
    return repairedY === undefined
      ? node
      : { ...node, position: { ...node.position, y: repairedY } };
  });
};

export const resolveDirectElementCollisionPadding = (
  entries = [],
  gapRatio = RESPONSIVE_ELEMENT_GAP_RATIO
) => {
  const paddingRatio = Math.max(0, finite(gapRatio, RESPONSIVE_ELEMENT_GAP_RATIO));
  const nodes = entries.map((entry, sourceIndex) => ({
    element: entry.element,
    flowRole: entry.flowRole,
    anchorElementId: entry.anchorElementId,
    anchorOffsetY: finite(entry.anchorOffsetY),
    sourceIndex,
    position: normalizePosition(entry.position),
  }));
  const underTextArtwork = nodes.filter((node) => node.flowRole === "underText");
  const foreground = nodes
    .filter((node) => node.flowRole !== "underText" && node.element?.layer !== "behindText")
    .sort(compareInReadingOrder);
  const placed = [];

  foreground.forEach((node) => {
    let nextY = node.position.y;
    let moved = true;

    while (moved) {
      moved = false;
      placed.forEach((previous) => {
        if (!horizontalRangesOverlap(node.position, previous.position)) return;
        const proportionalPadding = getCollisionPadding(
          node.element,
          previous.position.height,
          paddingRatio
        );
        const minimumY = previous.position.y + previous.position.height + proportionalPadding;
        if (nextY < minimumY && nextY + node.position.height > previous.position.y) {
          nextY = minimumY;
          moved = true;
        }
      });
      if (!UNDER_TEXT_CONTENT_TYPES.has(node.element?.type)) {
        underTextArtwork.forEach((artwork) => {
          if (!horizontalRangesOverlap(node.position, artwork.position)) return;
          if (node.position.y <= artwork.position.y) return;
          const proportionalPadding = getCollisionPadding(
            node.element,
            artwork.position.height,
            paddingRatio
          );
          const minimumY = artwork.position.y + artwork.position.height + proportionalPadding;
          if (nextY < minimumY && nextY + node.position.height > artwork.position.y) {
            nextY = minimumY;
            moved = true;
          }
        });
      }
    }

    node.position = { ...node.position, y: nextY };
    underTextArtwork.forEach((artwork) => {
      if (artwork.anchorElementId !== node.element?.id) return;
      artwork.position = {
        ...artwork.position,
        y: node.position.y + artwork.anchorOffsetY,
      };
    });
    placed.push(node);
  });

  return Object.fromEntries(nodes.map((node) => [node.element.id, { ...node.position }]));
};
