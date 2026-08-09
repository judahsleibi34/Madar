import {
  apiFetch,
  getApiUrl,
  readApiError,
  readApiResponse,
} from "../utils/apiClient";

const PUSH_SERVICE_WORKER_PATH = "/madar-push-sw.js";

export const fetchNotifications = async ({ limit = 30, unreadOnly = false, signal } = {}) => {
  const params = new URLSearchParams();
  params.set("limit", String(limit));

  if (unreadOnly) {
    params.set("unread_only", "true");
  }

  const response = await apiFetch(getApiUrl(`/notifications?${params.toString()}`), {
    method: "GET",
    cache: "no-store",
    signal,
  });
  const data = await readApiResponse(response);

  if (!response.ok) {
    throw new Error(readApiError(data, "Could not load notifications."));
  }

  return data;
};

export const markNotificationRead = async (notificationId) => {
  const response = await apiFetch(getApiUrl(`/notifications/${notificationId}/read`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const data = await readApiResponse(response);

  if (!response.ok) {
    throw new Error(readApiError(data, "Could not update notification."));
  }

  return data;
};

export const markAllNotificationsRead = async () => {
  const response = await apiFetch(getApiUrl("/notifications/read-all"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const data = await readApiResponse(response);

  if (!response.ok) {
    throw new Error(readApiError(data, "Could not update notifications."));
  }

  return data;
};

export const getPushPublicKey = async () => {
  const response = await apiFetch(getApiUrl("/notifications/push-public-key"), {
    method: "GET",
    cache: "no-store",
  });
  const data = await readApiResponse(response);

  if (!response.ok) {
    throw new Error(readApiError(data, "Could not load push settings."));
  }

  return data;
};

export const savePushSubscription = async (subscription) => {
  const response = await apiFetch(getApiUrl("/notifications/push-subscriptions"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(subscription),
  });
  const data = await readApiResponse(response);

  if (!response.ok) {
    throw new Error(readApiError(data, "Could not save push subscription."));
  }

  return data;
};

export const browserSupportsPush = () =>
  typeof window !== "undefined" &&
  "serviceWorker" in navigator &&
  "PushManager" in window &&
  "Notification" in window;

export const urlBase64ToUint8Array = (base64String) => {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = `${base64String}${padding}`.replace(/-/g, "+").replace(/_/g, "/");
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let index = 0; index < rawData.length; index += 1) {
    outputArray[index] = rawData.charCodeAt(index);
  }

  return outputArray;
};

export const enableBrowserPushNotifications = async () => {
  if (!browserSupportsPush()) {
    return { enabled: false, reason: "unsupported" };
  }

  const config = await getPushPublicKey();

  if (!config.enabled || !config.public_key) {
    return { enabled: false, reason: "server_not_configured" };
  }

  const permission = await Notification.requestPermission();

  if (permission !== "granted") {
    return { enabled: false, reason: "permission_denied" };
  }

  const registration = await navigator.serviceWorker.register(PUSH_SERVICE_WORKER_PATH);
  const existingSubscription = await registration.pushManager.getSubscription();
  const subscription = existingSubscription || await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(config.public_key),
  });

  await savePushSubscription(subscription.toJSON());
  return { enabled: true };
};

export const reconcileBrowserPushSubscription = async () => {
  if (!browserSupportsPush() || Notification.permission !== "granted") {
    return { reconciled: false };
  }

  const registration = await navigator.serviceWorker.getRegistration(PUSH_SERVICE_WORKER_PATH);
  const subscription = await registration?.pushManager.getSubscription();

  if (!subscription) {
    return { reconciled: false };
  }

  await savePushSubscription(subscription.toJSON());
  return { reconciled: true };
};
