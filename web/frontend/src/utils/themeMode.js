export function applyThemeMode() {
  document.documentElement.dataset.theme = "light";
  document.documentElement.style.colorScheme = "light";
  document.documentElement.classList.remove("theme-dark");
  document.documentElement.classList.add("theme-light");

  if (document.body) {
    document.body.classList.remove("theme-dark");
    document.body.classList.add("theme-light");
  }

  try {
    localStorage.setItem("madar-theme-mode", "light");
  } catch {
    // The interface remains light when storage is unavailable.
  }

  return "light";
}
