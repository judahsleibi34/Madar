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

export const getPageBuilderThemeVars = (theme = {}) => {
  const safeTheme = {
    mode: "light",
    background: "#f5f2ee",
    surface: "#ffffff",
    softSurface: "#fbfaf8",
    text: "#1a2744",
    muted: "#6d7484",
    primary: "#1a2744",
    accent: "var(--theme-primary)",
    accentDark: "var(--theme-primary-hover)",
    border: "rgba(26, 39, 68, 0.12)",
    radius: 18,
    fontFamily: "Inter",
    ...theme,
  };
  const formTheme = {
    background: safeTheme.background,
    surface: safeTheme.surface,
    inputBackground: "#ffffff",
    text: safeTheme.text,
    muted: safeTheme.muted,
    border: safeTheme.border,
    accent: safeTheme.accent,
    buttonText: "#ffffff",
    radius: 8,
    fieldRadius: 14,
    ...(safeTheme.form || {}),
  };
  const isDarkMode = safeTheme.mode === "dark";

  return {
    "--madar-bg": safeTheme.background,
    "--madar-surface": safeTheme.surface,
    "--madar-surface-soft": safeTheme.softSurface,
    "--madar-text": safeTheme.text,
    "--madar-muted": safeTheme.muted,
    "--madar-navy": safeTheme.primary,
    "--madar-red": safeTheme.accent,
    "--madar-red-dark": safeTheme.accentDark,
    "--madar-border": safeTheme.border,
    "--madar-border-strong":
      isDarkMode
        ? "rgba(244, 240, 232, 0.18)"
        : "rgba(26, 39, 68, 0.22)",
    "--madar-gradient": isDarkMode
      ? "var(--theme-gradient)"
      : `linear-gradient(135deg, ${safeTheme.primary} 0%, ${safeTheme.accent} 100%)`,
    "--madar-gradient-hover": isDarkMode
      ? "var(--theme-gradient-hover)"
      : `linear-gradient(135deg, ${safeTheme.primary} 0%, ${safeTheme.accentDark} 100%)`,
    "--madar-radius": `${safeTheme.radius}px`,
    "--form-theme-bg": formTheme.background,
    "--form-theme-surface": formTheme.surface,
    "--form-theme-input": formTheme.inputBackground,
    "--form-theme-text": formTheme.text,
    "--form-theme-muted": formTheme.muted,
    "--form-theme-border": formTheme.border,
    "--form-theme-accent": formTheme.accent,
    "--form-theme-button-text": formTheme.buttonText,
    "--form-theme-radius": `${formTheme.radius}px`,
    "--form-theme-field-radius": `${formTheme.fieldRadius}px`,
    fontFamily: safeTheme.fontFamily,
  };
};
