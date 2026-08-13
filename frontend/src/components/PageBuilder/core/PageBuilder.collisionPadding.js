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
        const proportionalPadding = Math.ceil(previous.position.height * paddingRatio);
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
          const proportionalPadding = Math.ceil(artwork.position.height * paddingRatio);
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

