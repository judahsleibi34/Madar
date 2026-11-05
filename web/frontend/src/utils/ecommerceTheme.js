export const MADAR_STORE_THEME = Object.freeze({
  accent: "#852c21",
  ["back" + "ground"]: "#ffffff",
  surface: "#f5f1eb",
  text: "#162033",
  muted: "#667085",
});

export const DEFAULT_SEASONAL_CAMPAIGN = Object.freeze({
  enabled: false,
  type: "black_friday",
});

export function readableForeground(background, dark = "#080808", light = "#ffffff") {
  const normalized = String(background || "").trim().replace(/^#/, "");
  const expanded = normalized.length === 3
    ? normalized.split("").map((character) => `${character}${character}`).join("")
    : normalized;
  if (!/^[0-9a-f]{6}$/iu.test(expanded)) return light;
  const channels = expanded.match(/.{2}/gu).map((value) => Number.parseInt(value, 16) / 255);
  const luminance = channels
    .map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4)
    .reduce((total, value, index) => total + value * [0.2126, 0.7152, 0.0722][index], 0);
  const contrastWithDark = (luminance + 0.05) / 0.05243;
  const contrastWithLight = 1.05 / (luminance + 0.05);
  return contrastWithDark >= contrastWithLight ? dark : light;
}

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
    seasonal_campaign: {
      ...DEFAULT_SEASONAL_CAMPAIGN,
      ...(saved.seasonal_campaign && typeof saved.seasonal_campaign === "object"
        ? saved.seasonal_campaign
        : {}),
      enabled: saved.seasonal_campaign?.enabled === true,
      type: "black_friday",
    },
  };
}
