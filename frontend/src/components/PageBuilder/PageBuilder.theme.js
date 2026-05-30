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
    accent: "#8b2a1a",
    accentDark: "#6e2014",
    border: "rgba(26, 39, 68, 0.12)",
    radius: 18,
    fontFamily: "Inter",
    ...theme,
  };

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
      safeTheme.mode === "dark"
        ? "rgba(255, 255, 255, 0.2)"
        : "rgba(26, 39, 68, 0.22)",
    "--madar-gradient": `linear-gradient(135deg, ${safeTheme.primary} 0%, ${safeTheme.accent} 100%)`,
    "--madar-gradient-hover": `linear-gradient(135deg, ${safeTheme.primary} 0%, ${safeTheme.accentDark} 100%)`,
    "--madar-radius": `${safeTheme.radius}px`,
    fontFamily: safeTheme.fontFamily,
  };
};
