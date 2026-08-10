import {
  apiFetch,
  getApiUrl,
  readApiError,
  readApiResponse,
} from "../utils/apiClient";
import {
  getExistingMadarPushEndpoint,
  getMadarServiceWorkerRegistration,
} from "../pwa/serviceWorker";
import { registerInstallation } from "../pwa/installation";
import {
  clearPushRotationNeeded,
  readPushRotationNeeded,
} from "../pwa/pushLifecycle";

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

export const savePushSubscription = async (subscription, installationId = null) => {
  const payload = installationId
    ? { ...subscription, installation_id: installationId }
    : subscription;
  const response = await apiFetch(getApiUrl("/notifications/push-subscriptions"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await readApiResponse(response);

  if (!response.ok) {
    throw new Error(readApiError(data, "Could not save push subscription."));
  }

  return data;
};

export const revokePushSubscription = async (endpoint) => {
  if (!endpoint) return { success: true, revoked_count: 0 };
  const response = await apiFetch(getApiUrl("/notifications/push-subscriptions"), {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint }),
  });
  const data = await readApiResponse(response);
  if (!response.ok) {
    throw new Error(readApiError(data, "Could not disable push subscription."));
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

export const enableBrowserPushNotifications = async ({ tenantId } = {}) => {
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

  const registration = await getMadarServiceWorkerRegistration();
  if (!registration) {
    return { enabled: false, reason: "unsupported" };
  }
  const existingSubscription = await registration.pushManager.getSubscription();
  const subscription = existingSubscription || await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(config.public_key),
  });

  const installation = tenantId
    ? await registerInstallation({ tenantId, force: true }).catch(() => null)
    : null;
  const installationId = installation?.installationId || null;
  await savePushSubscription(subscription.toJSON(), installationId);
  await clearPushRotationNeeded().catch(() => false);
  if (typeof registration.showNotification === "function") {
    await registration.showNotification("Madar notifications enabled", {
      body: "Calendar reminders can now appear on this device when Madar is closed.",
      icon: "/pwa-icon-192.png",
      badge: "/pwa-icon-192.png",
      tag: "madar-push-enabled",
      data: {
        action: { kind: "notification_center", path: "/notifications" },
      },
    });
  }
  return { enabled: true };
};

export const reconcileBrowserPushLifecycle = async ({
  tenantId,
  installation: suppliedInstallation = null,
} = {}) => {
  if (!browserSupportsPush()) {
    return { reconciled: false, reason: "unsupported" };
  }
  const rotationNeeded = await readPushRotationNeeded().catch(() => false);
  if (Notification.permission !== "granted") {
    const existingEndpoint = await getExistingMadarPushEndpoint().catch(() => null);
    if (existingEndpoint) {
      await revokePushSubscription(existingEndpoint).catch(() => null);
    }
    await clearPushRotationNeeded().catch(() => false);
    return { reconciled: false, reason: Notification.permission };
  }

  const registration = await getMadarServiceWorkerRegistration();
  let subscription = await registration?.pushManager.getSubscription();
  const installation = suppliedInstallation || (tenantId
    ? await registerInstallation({ tenantId, force: true }).catch(() => null)
    : null);
  const installationId = installation?.installationId || null;
  const explicitlyEnabled = installation?.installation?.notifications_enabled === true;

  if (!subscription && explicitlyEnabled) {
    const config = await getPushPublicKey();
    if (config.enabled && config.public_key) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(config.public_key),
      });
    }
  }
  if (!subscription) {
    await clearPushRotationNeeded().catch(() => false);
    return {
      reconciled: false,
      reason: rotationNeeded ? "rotation_without_opt_in" : "subscription_missing",
    };
  }

  await savePushSubscription(subscription.toJSON(), installationId);
  await clearPushRotationNeeded().catch(() => false);
  return { reconciled: true, restored: explicitlyEnabled };
};

export const reconcileBrowserPushSubscription = reconcileBrowserPushLifecycle;
