export const MADAR_STORE_THEME = Object.freeze({
  accent: "#852c21",
  ["back" + "ground"]: "#ffffff",
  surface: "#f5f1eb",
  text: "#162033",
  muted: "#667085",
});

const LEGACY_DEFAULT_STORE_THEME = Object.freeze({
  accent: "#2463eb",
  ["back" + "ground"]: "#ffffff",
  surface: "#f7f8fa",
  text: "#151821",
  muted: "#697181",
});

export function normalizeStoreTheme(theme) {
  const saved = theme && typeof theme === "object" ? theme : {};
  const isLegacyDefault = Object.entries(LEGACY_DEFAULT_STORE_THEME)
    .every(([key, value]) => saved[key] === value);
  return {
    ...MADAR_STORE_THEME,
    ...(isLegacyDefault ? {} : saved),
  };
}
