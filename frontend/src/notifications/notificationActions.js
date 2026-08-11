const NOTIFICATION_CENTER_PATH = "/notifications";
const CALENDAR_PATH = "/calendar";
const ACTION_KINDS = new Set([
  "notification_center",
  "reservation",
  "calendar_event",
  "calendar_task",
  "form_submission",
]);

export function getSafeNotificationActionPath(value) {
  const action = value && typeof value === "object" ? value : {};
  const kind = ACTION_KINDS.has(action.kind) ? action.kind : "notification_center";
  const expectedPath = kind === "calendar_event" || kind === "calendar_task"
    ? CALENDAR_PATH
    : NOTIFICATION_CENTER_PATH;
  const rawPath = typeof action.path === "string" ? action.path : "";

  if (
    !rawPath
    || rawPath.length > 300
    || !rawPath.startsWith("/")
    || rawPath.startsWith("//")
    || rawPath.includes("\\")
    || rawPath.includes("?")
    || rawPath.includes("#")
  ) {
    return NOTIFICATION_CENTER_PATH;
  }

  try {
    const parsed = new URL(rawPath, window.location.origin);
    if (parsed.origin !== window.location.origin || parsed.pathname !== expectedPath) {
      return NOTIFICATION_CENTER_PATH;
    }
  } catch {
    return NOTIFICATION_CENTER_PATH;
  }

  return expectedPath;
}

export { ACTION_KINDS, CALENDAR_PATH, NOTIFICATION_CENTER_PATH };
