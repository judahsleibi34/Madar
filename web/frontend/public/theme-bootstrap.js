(() => {
  const root = document.documentElement;
  let mode;

  try {
    mode = localStorage.getItem("madar-theme-mode") === "dark" ? "dark" : "light";
  } catch {
    mode = "light";
  }

  const themeClass = mode === "dark" ? "theme-dark" : "theme-light";
  const otherThemeClass = mode === "dark" ? "theme-light" : "theme-dark";
  root.dataset.theme = mode;
  root.classList.remove(otherThemeClass);
  root.classList.add(themeClass);
  root.style.colorScheme = mode;

  const applyBodyTheme = () => {
    if (!document.body) return false;
    document.body.classList.remove(otherThemeClass);
    document.body.classList.add(themeClass);
    return true;
  };

  if (!applyBodyTheme()) {
    const observer = new MutationObserver(() => {
      if (applyBodyTheme()) observer.disconnect();
    });
    observer.observe(root, { childList: true, subtree: true });
  }
})();
