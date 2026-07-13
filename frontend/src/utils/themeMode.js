export const MADAR_THEME_STORAGE_KEY = "madar-theme-mode";

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
    const stored = localStorage.getItem(MADAR_THEME_STORAGE_KEY);
    return stored === "dark" || stored === "light" ? stored : "light";
  } catch {
    return "light";
  }
}

export function applyThemeMode(mode, { emit = true, persist = true } = {}) {
  const safeMode = normalizeThemeMode(mode);
  const activeTheme = SUPPORTED_THEME_MODES[safeMode];
  const previousMode = document.documentElement.dataset.theme;

  document.documentElement.dataset.theme = safeMode;
  document.documentElement.style.colorScheme = activeTheme.colorScheme;

  Object.values(SUPPORTED_THEME_MODES).forEach(({ className }) => {
    document.documentElement.classList.toggle(className, className === activeTheme.className);
  });

  if (document.body) {
    Object.values(SUPPORTED_THEME_MODES).forEach(({ className }) => {
      document.body.classList.toggle(className, className === activeTheme.className);
    });
  }

  if (persist) {
    try {
      localStorage.setItem(MADAR_THEME_STORAGE_KEY, safeMode);
    } catch {
      // Ignore localStorage errors.
    }
  }

  if (emit && previousMode !== safeMode) {
    window.dispatchEvent(
      new CustomEvent("madar-theme-change", {
        detail: { mode: safeMode },
      })
    );
  }

  return safeMode;
}

export function transitionThemeMode(mode) {
  const safeMode = normalizeThemeMode(mode);
  if (document.documentElement.dataset.theme === safeMode) return safeMode;

  const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  if (!reduceMotion && typeof document.startViewTransition === "function") {
    document.startViewTransition(() => applyThemeMode(safeMode));
    return safeMode;
  }

  if (!reduceMotion) {
    document.documentElement.classList.add("theme-transitioning");
    window.requestAnimationFrame(() => {
      applyThemeMode(safeMode);
      window.setTimeout(() => {
        document.documentElement.classList.remove("theme-transitioning");
      }, 170);
    });
    return safeMode;
  }

  return applyThemeMode(safeMode);
}
