export const notificationProviderConstants = {
  FETCH_LIMIT: 50,
  MAX_KNOWN_IDS: 500,
  MAX_SESSION_DEDUP: 300,
  MAX_TOAST_QUEUE: 50,
  POLL_INTERVAL_MS: 15_000,
  SESSION_DEDUP_TTL_MS: 24 * 60 * 60 * 1000,
};

const SESSION_KEY_PREFIX = "madar-notification-toast-session-v1:";

export const getNotificationIdentity = (user) => {
  const tenantId = String(user?.tenant_id || "").trim();
  const userId = String(user?.id || user?.auth_id || "").trim();
  return tenantId && userId ? `${tenantId}:${userId}` : "";
};

export const normalizeNotification = (item) => ({
  id: String(item?.id || ""),
  eventId: String(item?.event_id || ""),
  tenantId: String(item?.tenant_id || ""),
  eventType: String(item?.event_type || ""),
  title: String(item?.title || ""),
  detail: String(item?.body || item?.detail || ""),
  time: item?.time || "",
  createdAt: item?.created_at || "",
  group: item?.group || "",
  source: item?.source || item?.event_type || "",
  unread: item?.unread !== false && !item?.read_at,
  readAt: item?.read_at || null,
  data: item?.data && typeof item.data === "object" ? item.data : {},
});

export const notificationKey = (identity, notificationId) => `${identity}:${notificationId}`;

export const readSessionDedup = (identity, storage = globalThis.sessionStorage) => {
  if (!identity || !storage) return new Set();
  try {
    const now = Date.now();
    const parsed = JSON.parse(storage.getItem(`${SESSION_KEY_PREFIX}${identity}`) || "[]");
    return new Set((Array.isArray(parsed) ? parsed : [])
      .filter((item) => (
        item?.key
        && now - Number(item.at || 0) < notificationProviderConstants.SESSION_DEDUP_TTL_MS
      ))
      .slice(-notificationProviderConstants.MAX_SESSION_DEDUP)
      .map((item) => item.key));
  } catch {
    return new Set();
  }
};

export const rememberSessionDedup = (
  identity,
  key,
  storage = globalThis.sessionStorage,
) => {
  if (!identity || !key || !storage) return;
  try {
    const storageKey = `${SESSION_KEY_PREFIX}${identity}`;
    const now = Date.now();
    const parsed = JSON.parse(storage.getItem(storageKey) || "[]");
    const entries = (Array.isArray(parsed) ? parsed : [])
      .filter((item) => (
        item?.key !== key
        && now - Number(item?.at || 0) < notificationProviderConstants.SESSION_DEDUP_TTL_MS
      ));
    entries.push({ key, at: now });
    storage.setItem(
      storageKey,
      JSON.stringify(entries.slice(-notificationProviderConstants.MAX_SESSION_DEDUP)),
    );
  } catch {
    // Session storage is an optional replay guard, never a prerequisite.
  }
};

export const chronologicalNotifications = (items) => [...items].sort((left, right) => {
  const leftTime = Date.parse(left.createdAt || left.time || "") || 0;
  const rightTime = Date.parse(right.createdAt || right.time || "") || 0;
  return leftTime - rightTime || left.id.localeCompare(right.id);
});
