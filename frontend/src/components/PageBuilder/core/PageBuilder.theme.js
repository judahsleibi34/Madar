import { themePresets } from "./PageBuilder.constants";

export const getThemePreset = (mode = "light") => {
  return themePresets[mode] || themePresets.light;
};

export const applyThemeModeToProject = (project, mode = "light") => {
  const preset = getThemePreset(mode);

  return {
    ...project,
    theme: {
      ...project.theme,
      ...preset,
      mode,
    },
  };
};

export const getPageBuilderThemeClassName = ({ mode = "light", preview = false } = {}) => {
  return `page-builder theme-${mode || "light"} ${preview ? "preview-mode" : ""}`;
};

export const defaultWebsiteTheme = {
  background: "#f4f0e8",
  softSurface: "#f8f4ed",
  surface: "#fffdfa",
  headerBackground: "",
  text: "#162033",
  muted: "#6f7787",
  primary: "#162033",
  accent: "#852c21",
  accentDark: "#6f241b",
  buttonText: "#ffffff",
  border: "rgba(27, 42, 74, 0.12)",
};

export const defaultFormTheme = {
  background: "#f4f0e8",
  surface: "#fffdfa",
  inputBackground: "#f8f4ed",
  text: "#162033",
  muted: "#6f7787",
  border: "#ddd6ca",
  accent: "#852c21",
  buttonText: "#ffffff",
  radius: 8,
  fieldRadius: 14,
};

const isHexColor = (value) => /^#[0-9a-f]{6}$/i.test(String(value || ""));

const resolveThemeColor = (value, fallback) =>
  isHexColor(value) ? String(value).toLowerCase() : fallback;

const hexToRgb = (hex, fallback = "27, 42, 74") => {
  if (!isHexColor(hex)) return fallback;

  const normalized = hex.replace("#", "");
  const r = parseInt(normalized.slice(0, 2), 16);
  const g = parseInt(normalized.slice(2, 4), 16);
  const b = parseInt(normalized.slice(4, 6), 16);

  return `${r}, ${g}, ${b}`;
};

const getSafeWebsiteTheme = (theme = {}) => ({
  mode: "light",
  ...defaultWebsiteTheme,
  radius: 18,
  fontFamily: "Inter",
  ...theme,
});

const getThemeFontStack = (fontFamily) => {
  const selectedFont = String(fontFamily || "Inter").trim() || "Inter";
  return `${JSON.stringify(selectedFont)}, "IBM Plex Sans Arabic", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
};

const getSafeFormTheme = (theme = {}) => ({
  ...defaultFormTheme,
  ...((theme || {}).form || {}),
});

export const getWebsiteThemeVars = (theme = {}) => {
  const safeTheme = getSafeWebsiteTheme(theme);
  const websiteTheme = {
    background: resolveThemeColor(safeTheme.background, defaultWebsiteTheme.background),
    softSurface: resolveThemeColor(safeTheme.softSurface, defaultWebsiteTheme.softSurface),
    surface: resolveThemeColor(safeTheme.surface, defaultWebsiteTheme.surface),
    headerBackground: resolveThemeColor(
      safeTheme.headerBackground,
      resolveThemeColor(safeTheme.surface, defaultWebsiteTheme.headerBackground)
    ),
    text: resolveThemeColor(safeTheme.text, defaultWebsiteTheme.text),
    muted: resolveThemeColor(safeTheme.muted, defaultWebsiteTheme.muted),
    primary: resolveThemeColor(safeTheme.primary, defaultWebsiteTheme.primary),
    accent: resolveThemeColor(safeTheme.accent, defaultWebsiteTheme.accent),
    accentDark: resolveThemeColor(safeTheme.accentDark, defaultWebsiteTheme.accentDark),
    buttonText: resolveThemeColor(safeTheme.buttonText, defaultWebsiteTheme.buttonText),
  };
  const isDarkMode = safeTheme.mode === "dark";
  const shadowRgb = isDarkMode ? "4, 8, 16" : hexToRgb(websiteTheme.primary);
  const primaryRgb = hexToRgb(websiteTheme.accent, "133, 44, 33");
  const borderColor = isHexColor(safeTheme.border)
    ? safeTheme.border
    : `rgba(${shadowRgb}, 0.12)`;

  return {
    "--theme-bg": websiteTheme.background,
    "--theme-bg-soft": websiteTheme.softSurface,
    "--theme-surface": websiteTheme.surface,
    "--theme-header-background": websiteTheme.headerBackground,
    "--theme-surface-elevated": websiteTheme.softSurface,
    "--theme-surface-2": websiteTheme.softSurface,
    "--theme-surface-3": websiteTheme.softSurface,
    "--theme-text": websiteTheme.text,
    "--theme-text-soft": websiteTheme.muted,
    "--theme-text-muted": websiteTheme.muted,
    "--theme-text-inverse": websiteTheme.buttonText,
    "--theme-text-inverse-rgb": hexToRgb(websiteTheme.buttonText, "255, 255, 255"),
    "--theme-primary": websiteTheme.accent,
    "--theme-primary-hover": websiteTheme.accentDark,
    "--theme-on-primary": websiteTheme.buttonText,
    "--theme-primary-soft": `rgba(${primaryRgb}, 0.1)`,
    "--theme-primary-rgb": primaryRgb,
    "--theme-border": borderColor,
    "--theme-border-strong": `rgba(${shadowRgb}, 0.22)`,
    "--theme-info": "#2563eb",
    "--theme-warning": "#b45309",
    "--theme-danger": "#b42318",
    "--theme-black-rgb": "0, 0, 0",
    "--theme-gradient": websiteTheme.accent,
    "--theme-gradient-hover": websiteTheme.accentDark,
    "--theme-text-gradient": websiteTheme.accent,
    "--theme-shadow-rgb": shadowRgb,
    "--action-primary": websiteTheme.accent,
    "--action-primary-hover": websiteTheme.accentDark,
    "--madar-bg": websiteTheme.background,
    "--madar-surface": websiteTheme.surface,
    "--madar-surface-soft": websiteTheme.softSurface,
    "--madar-text": websiteTheme.text,
    "--madar-muted": websiteTheme.muted,
    "--madar-navy": websiteTheme.primary,
    "--madar-red": websiteTheme.accent,
    "--madar-red-dark": websiteTheme.accentDark,
    "--madar-border": borderColor,
    "--madar-border-strong":
      isDarkMode
        ? "rgba(244, 240, 232, 0.18)"
        : `rgba(${shadowRgb}, 0.22)`,
    "--madar-gradient": websiteTheme.accent,
    "--madar-gradient-hover": websiteTheme.accentDark,
    "--madar-radius": `${safeTheme.radius}px`,
    "--theme-font-family": getThemeFontStack(safeTheme.fontFamily),
    fontFamily: getThemeFontStack(safeTheme.fontFamily),
  };
};

export const getFormThemeVars = (theme = {}) => {
  const formTheme = getSafeFormTheme(theme);

  return {
    "--form-theme-bg": resolveThemeColor(formTheme.background, defaultFormTheme.background),
    "--form-theme-surface": resolveThemeColor(formTheme.surface, defaultFormTheme.surface),
    "--form-theme-input": resolveThemeColor(formTheme.inputBackground, defaultFormTheme.inputBackground),
    "--form-theme-text": resolveThemeColor(formTheme.text, defaultFormTheme.text),
    "--form-theme-muted": resolveThemeColor(formTheme.muted, defaultFormTheme.muted),
    "--form-theme-border": resolveThemeColor(formTheme.border, defaultFormTheme.border),
    "--form-theme-accent": resolveThemeColor(formTheme.accent, defaultFormTheme.accent),
    "--form-theme-button-text": resolveThemeColor(formTheme.buttonText, defaultFormTheme.buttonText),
    "--form-theme-radius": `${formTheme.radius}px`,
    "--form-theme-field-radius": `${formTheme.fieldRadius}px`,
  };
};

export const getPageBuilderThemeVars = (theme = {}) => ({
  ...getWebsiteThemeVars(theme),
  ...getFormThemeVars(theme),
});
