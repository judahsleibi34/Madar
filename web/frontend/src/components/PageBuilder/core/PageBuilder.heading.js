const supportedHeadingTags = new Set(["h1", "h2", "h3"]);

export const getElementHeadingTag = (element = {}) => {
  const rawLevel = String(element.headingLevel || "").trim().toLowerCase();
  if (supportedHeadingTags.has(rawLevel)) return rawLevel;

  const numericLevel = Number(element.headingLevel);
  if (Number.isInteger(numericLevel) && numericLevel >= 1 && numericLevel <= 3) {
    return `h${numericLevel}`;
  }

  return "h1";
};

export const getHeadingLevelFromFormat = (format) => {
  const normalized = String(format || "").trim().toLowerCase();
  return supportedHeadingTags.has(normalized) ? Number(normalized.slice(1)) : null;
};
