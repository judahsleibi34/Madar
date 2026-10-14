(() => {
  const root = document.documentElement;
  root.dataset.theme = "light";
  root.classList.remove("theme-dark");
  root.classList.add("theme-light");
  root.style.colorScheme = "light";

  try {
    localStorage.setItem("madar-theme-mode", "light");
  } catch {
    // The interface remains light when storage is unavailable.
  }

  const applyBodyTheme = () => {
    if (!document.body) return false;
    document.body.classList.remove("theme-dark");
    document.body.classList.add("theme-light");
    return true;
  };

  if (!applyBodyTheme()) {
    const observer = new MutationObserver(() => {
      if (applyBodyTheme()) observer.disconnect();
    });
    observer.observe(root, { childList: true, subtree: true });
  }
})();
