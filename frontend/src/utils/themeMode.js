export const MADAR_THEME_STORAGE_KEY = "madar-theme-mode";
const MADAR_LIGHT_THEME_RESTORE_KEY = "madar-light-theme-restored-v1";

export const SUPPORTED_THEME_MODES = {
  light: {
    label: "Light",
    colorScheme: "light",
    className: "theme-light",
  },
  dark: {
    label: "Dark",
    colorScheme: "dark",
    className: "theme-dark",
  },
};

export function normalizeThemeMode(mode) {
  return SUPPORTED_THEME_MODES[mode] ? mode : "light";
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
  const activeTheme = SUPPORTED_THEME_MODES[safeMode];

  document.documentElement.dataset.theme = safeMode;

  Object.values(SUPPORTED_THEME_MODES).forEach(({ className }) => {
    document.documentElement.classList.remove(className);
  });

  document.documentElement.classList.add(activeTheme.className);

  if (document.body) {
    Object.values(SUPPORTED_THEME_MODES).forEach(({ className }) => {
      document.body.classList.remove(className);
    });

    document.body.classList.add(activeTheme.className);
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
