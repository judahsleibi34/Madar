const NOTIFICATION_CENTER_PATH = "/notifications";
const CALENDAR_PATH = "/calendar";
const ACTION_KINDS = new Set([
  "notification_center",
  "learning",
  "reservation",
  "calendar_event",
  "calendar_task",
  "form_submission",
]);

export function resolveNotificationAction(value, { tenantId } = {}) {
  const action = value && typeof value === "object" ? value : {};
  const kind = ACTION_KINDS.has(action.kind) ? action.kind : "notification_center";
  const learningPath = /^\/(?:my-learning(?:\/(?:dashboard|assessment-reviews(?:\/[0-9a-f-]{36})?|affiliate(?:\/application)?|exchange(?:\/[0-9a-f-]{36})?|form-responses(?:\/[0-9a-f-]{36})?|referrals|rewards|wallet|withdrawals|account|plans|notifications|programmes|certificates(?:\/[0-9a-f-]{36})?|courses\/[0-9a-f-]{36}(?:\/(?:lessons|assessments)\/[0-9a-f-]{36})?))?|e-learning(?:\/(?:programmes|reports|forms\/responses(?:\/[0-9a-f-]{36})?))?)$/;
  const expectedPath = kind === "learning" ? (learningPath.test(action.path || "") ? action.path : "/my-learning") : kind === "calendar_event" || kind === "calendar_task"
    ? CALENDAR_PATH
    : NOTIFICATION_CENTER_PATH;
  const rawPath = typeof action.path === "string" ? action.path : "";
  const targetTenantId = String(action.tenant_id || "").trim();
  if (targetTenantId && String(tenantId || "").trim() !== targetTenantId) {
    return { kind: "notification_center", path: NOTIFICATION_CENTER_PATH };
  }

  if (
    !rawPath
    || rawPath.length > 300
    || !rawPath.startsWith("/")
    || rawPath.startsWith("//")
    || rawPath.includes("\\")
    || rawPath.includes("?")
    || rawPath.includes("#")
  ) {
    return { kind: "notification_center", path: NOTIFICATION_CENTER_PATH };
  }

  try {
    const parsed = new URL(rawPath, window.location.origin);
    if (parsed.origin !== window.location.origin || parsed.pathname !== expectedPath) {
      return { kind: "notification_center", path: NOTIFICATION_CENTER_PATH };
    }
  } catch {
    return { kind: "notification_center", path: NOTIFICATION_CENTER_PATH };
  }

  return { kind, path: expectedPath };
}

export function getSafeNotificationActionPath(value, options) {
  return resolveNotificationAction(value, options).path;
}

export { ACTION_KINDS, CALENDAR_PATH, NOTIFICATION_CENTER_PATH };
