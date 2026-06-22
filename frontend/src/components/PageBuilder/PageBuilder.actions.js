export const runElementActionWithHandlers = ({
  element,
  selectPage,
  getStoredUrlError,
  showToast,
}) => {
  const action = element.action || {};

  if (action.type === "goToPage" && action.pageId) {
    selectPage(action.pageId);
    return;
  }

  if (action.type === "openUrl" && action.url) {
    const urlError = getStoredUrlError(action.url, {
      fieldName: "Button action URL",
      allowRelative: true,
    });

    if (urlError) {
      showToast(urlError);
      return;
    }

    window.open(action.url, "_blank", "noopener,noreferrer");
    return;
  }

  if (action.type === "showMessage" && action.message) {
    showToast(action.message);
  }
};

export const getDirectFrameAtPoint = (clientX, clientY) => {
  const frames = Array.from(document.querySelectorAll(".direct-layout-frame"));

  return (
    frames.find((frame) => {
      const rect = frame.getBoundingClientRect();
      return (
        clientX >= rect.left &&
        clientX <= rect.right &&
        clientY >= rect.top &&
        clientY <= rect.bottom
      );
    }) || null
  );
};

