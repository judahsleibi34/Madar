export const requestBuilderUnloadWarning = (event, hasUnsavedWork) => {
  if (!hasUnsavedWork) return false;

  event.preventDefault();
  // Chrome still requires a truthy legacy returnValue in addition to
  // preventDefault(). The browser intentionally controls the prompt text.
  event.returnValue = true;
  return true;
};
export const isBuilderReloadShortcut = (event) =>
  Boolean(
    event?.key === "F5" ||
    ((event?.ctrlKey || event?.metaKey) && String(event?.key || "").toLowerCase() === "r")
  );
