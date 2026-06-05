export const MADAR_THEME_STORAGE_KEY = "madar-theme-mode";
const MADAR_LIGHT_THEME_RESTORE_KEY = "madar-light-theme-restored-v1";

export function normalizeThemeMode(mode) {
  return mode === "dark" ? "dark" : "light";
}

export function readStoredThemeMode() {
  try {
    if (localStorage.getItem(MADAR_LIGHT_THEME_RESTORE_KEY) !== "true") {
      localStorage.setItem(MADAR_THEME_STORAGE_KEY, "light");
      localStorage.setItem(MADAR_LIGHT_THEME_RESTORE_KEY, "true");
      return "light";
    }

    const stored = localStorage.getItem(MADAR_THEME_STORAGE_KEY);
    return stored === "dark" || stored === "light" ? stored : "light";
  } catch {
    return "light";
  }
}

export function applyThemeMode(mode) {
  const safeMode = normalizeThemeMode(mode);

  document.documentElement.dataset.theme = safeMode;
  document.documentElement.classList.toggle("theme-dark", safeMode === "dark");

  if (document.body) {
    document.body.classList.toggle("theme-dark", safeMode === "dark");
  }

  try {
    localStorage.setItem(MADAR_THEME_STORAGE_KEY, safeMode);
  } catch {
    // Ignore localStorage errors.
  }

  window.dispatchEvent(
    new CustomEvent("madar-theme-change", {
      detail: { mode: safeMode },
    })
  );

  return safeMode;
}
