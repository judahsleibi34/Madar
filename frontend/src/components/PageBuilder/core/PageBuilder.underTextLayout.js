const TEXT_TYPES = new Set(["heading", "text", "list"]);

const finite = (value) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
};

const normalizeRect = (position = {}) => ({
  x: finite(position.x),
  y: finite(position.y),
  width: Math.max(1, finite(position.width)),
  height: Math.max(1, finite(position.height)),
});

const intersectionArea = (first, second) => {
  const width = Math.max(
    0,
    Math.min(first.x + first.width, second.x + second.width) - Math.max(first.x, second.x)
  );
  const height = Math.max(
    0,
    Math.min(first.y + first.height, second.y + second.height) - Math.max(first.y, second.y)
  );
  return width * height;
};

/**
 * Under-text intent is authored on desktop and then carried to every viewport.
 * Explicit layering is authoritative; older projects are repaired in memory
 * when an image meaningfully overlaps a text component.
 */
export const getUnderTextImageRelationships = (desktopEntries = []) => {
  const entries = desktopEntries.map((entry) => ({
    ...entry,
    position: normalizeRect(entry.position),
  }));
  const textEntries = entries.filter((entry) => TEXT_TYPES.has(entry.element?.type));
  const relationships = new Map();

  entries.forEach((entry) => {
    if (entry.element?.type !== "image") return;
    const imageArea = entry.position.width * entry.position.height;
    const candidates = textEntries.map((textEntry) => {
      const textArea = textEntry.position.width * textEntry.position.height;
      const overlap = intersectionArea(entry.position, textEntry.position);
      return {
        textEntry,
        overlap,
        overlapRatio: overlap / Math.max(1, Math.min(imageArea, textArea)),
      };
    }).filter((candidate) => candidate.overlapRatio >= 0.15)
      .sort((first, second) => second.overlap - first.overlap);
    const anchor = candidates[0]?.textEntry;
    if (entry.element?.layer !== "behindText" && !anchor) return;
    relationships.set(entry.element.id, {
      anchorElementId: anchor?.element?.id || null,
      offsetX: anchor ? entry.position.x - anchor.position.x : 0,
      offsetY: anchor ? entry.position.y - anchor.position.y : 0,
    });
  });

  return relationships;
};

export const getUnderTextImageIds = (desktopEntries = []) =>
  new Set(getUnderTextImageRelationships(desktopEntries).keys());


/** Keep background artwork attached to its authored desktop geometry. */
export const projectUnderTextImagePosition = (
  desktopPosition = {},
  targetWidth = 1200,
  desktopWidth = 1200
) => {
  const ratio = Math.max(1, finite(targetWidth)) / Math.max(1, finite(desktopWidth));
  const desktopRect = normalizeRect(desktopPosition);
  return {
    ...desktopPosition,
    x: desktopRect.x * ratio,
    y: desktopRect.y * ratio,
    width: desktopRect.width * ratio,
    height: desktopRect.height * ratio,
  };
};
