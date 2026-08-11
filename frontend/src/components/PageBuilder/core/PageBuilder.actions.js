const canonicalActionTypes = new Map([
  ["page", "goToPage"],
  ["gotopage", "goToPage"],
  ["internal", "goToPage"],
  ["url", "openUrl"],
  ["openurl", "openUrl"],
  ["external", "openUrl"],
  ["message", "showMessage"],
  ["showmessage", "showMessage"],
  ["none", "none"],
]);

export const normalizeElementAction = (value = {}) => {
  const action = value && typeof value === "object" && !Array.isArray(value) ? value : {};
  const rawType = String(action.type || action.actionType || action.action_type || "none").trim();
  const type = canonicalActionTypes.get(rawType.toLowerCase()) || "none";

  return {
    type,
    pageId: String(action.pageId || action.targetPageId || action.page_id || "").trim(),
    sectionId: String(action.sectionId || action.section_id || "").trim(),
    formId: String(action.formId || action.form_id || "").trim(),
    url: String(action.url || action.href || "").trim(),
    message: String(action.message || ""),
    status: String(action.status || ""),
    openInNewTab: action.openInNewTab ?? action.newTab ?? action.target !== "_self",
  };
};

export const getButtonActionIssue = ({ element, pages = [], getStoredUrlError }) => {
  if (!["button", "imageButton"].includes(element?.type)) return null;
  const action = normalizeElementAction(element.action);

  if (action.type === "goToPage" && !pages.some((page) => String(page?.id || "") === action.pageId)) {
    return { issue_type: "invalid_button_page_target", action_type: action.type };
  }
  if (action.type === "openUrl") {
    const error = getStoredUrlError?.(action.url, {
      fieldName: "Button action URL",
      allowRelative: false,
      allowEmpty: false,
    });
    if (error) return { issue_type: "invalid_button_url", action_type: action.type, message: error };
  }
  if (action.type === "showMessage" && !action.message.trim()) {
    return { issue_type: "empty_button_message", action_type: action.type };
  }
  return null;
};

export const runPublicElementAction = ({
  element,
  pages = [],
  goToPage,
  getStoredUrlError,
  openExternal,
  showMessage,
  showUnavailable,
}) => {
  const action = normalizeElementAction(element?.action);
  const issue = getButtonActionIssue({ element, pages, getStoredUrlError });
  if (issue) {
    showUnavailable?.("This button action is unavailable.");
    return { handled: false, issue };
  }

  if (action.type === "goToPage") {
    const page = pages.find((item) => String(item?.id || "") === action.pageId);
    goToPage?.(page);
    return { handled: true, type: action.type };
  }
  if (action.type === "openUrl") {
    openExternal?.(action.url, action.openInNewTab !== false);
    return { handled: true, type: action.type };
  }
  if (action.type === "showMessage") {
    showMessage?.(action.message);
    return { handled: true, type: action.type };
  }

  showUnavailable?.("This button has no action configured.");
  return { handled: false, issue: { issue_type: "missing_button_action", action_type: action.type } };
};

export const runElementActionWithHandlers = ({
  element,
  selectPage,
  getStoredUrlError,
  showToast,
}) => {
  const action = normalizeElementAction(element.action);

  if (action.type === "goToPage" && action.pageId) {
    selectPage(action.pageId);
    return;
  }

  if (action.type === "openUrl" && action.url) {
    const urlError = getStoredUrlError(action.url, {
      fieldName: "Button action URL",
      allowRelative: false,
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
