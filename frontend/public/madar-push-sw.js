const MADAR_NOTIFICATION_FALLBACK_PATH = "/notifications";
const MADAR_ACTION_KINDS = new Set([
  "notification_center",
  "reservation",
  "calendar_event",
  "calendar_task",
  "form_submission",
]);
const MADAR_PUSH_LIFECYCLE_DB = "madar-push-lifecycle";
const MADAR_PUSH_LIFECYCLE_STORE = "state";
const MADAR_ROTATION_KEY = "rotation-needed";

function normalizeNotificationAction(value) {
  const candidate = value && typeof value === "object" ? value : {};
  const kind = MADAR_ACTION_KINDS.has(candidate.kind)
    ? candidate.kind
    : "notification_center";
  const rawPath = typeof candidate.path === "string"
    ? candidate.path
    : MADAR_NOTIFICATION_FALLBACK_PATH;
  if (
    rawPath.length > 300
    || !rawPath.startsWith("/")
    || rawPath.startsWith("//")
    || rawPath.includes("\\")
    || rawPath.includes("#")
    || rawPath.includes("?")
  ) {
    return { kind: "notification_center", path: MADAR_NOTIFICATION_FALLBACK_PATH };
  }
  try {
    const target = new URL(rawPath, self.location.origin);
    if (
      target.origin !== self.location.origin
      || target.pathname !== MADAR_NOTIFICATION_FALLBACK_PATH
    ) {
      return { kind: "notification_center", path: MADAR_NOTIFICATION_FALLBACK_PATH };
    }
  } catch {
    return { kind: "notification_center", path: MADAR_NOTIFICATION_FALLBACK_PATH };
  }
  const action = { kind, path: MADAR_NOTIFICATION_FALLBACK_PATH };
  if (
    typeof candidate.object_id === "string"
    && /^[A-Za-z0-9_.:-]{1,200}$/.test(candidate.object_id)
  ) {
    action.object_id = candidate.object_id;
  }
  return action;
}

function openPushLifecycleDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(MADAR_PUSH_LIFECYCLE_DB, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(MADAR_PUSH_LIFECYCLE_STORE)) {
        request.result.createObjectStore(MADAR_PUSH_LIFECYCLE_STORE);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function markPushRotationNeeded() {
  const database = await openPushLifecycleDatabase();
  try {
    await new Promise((resolve, reject) => {
      const transaction = database.transaction(MADAR_PUSH_LIFECYCLE_STORE, "readwrite");
      transaction.objectStore(MADAR_PUSH_LIFECYCLE_STORE).put(
        { needed: true, occurred_at: Date.now() },
        MADAR_ROTATION_KEY,
      );
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
  } finally {
    database.close();
  }
}

self.addEventListener("install", (event) => {
  // This worker owns no caches or in-flight application state, so activating
  // an update immediately cannot expose stale tenant or authenticated data.
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = {};
  }
  const action = normalizeNotificationAction(payload.data?.action);
  const options = {
    body: typeof payload.body === "string" && payload.body
      ? payload.body.slice(0, 240)
      : "Open Madar to view details.",
    icon: "/pwa-icon-192.png",
    badge: "/pwa-icon-192.png",
    data: { action },
  };
  if (typeof payload.tag === "string" && /^madar-event:[A-Za-z0-9-]{1,100}$/.test(payload.tag)) {
    options.tag = payload.tag;
  }
  const title = typeof payload.title === "string" && payload.title
    ? payload.title.slice(0, 120)
    : "Madar notification";
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("pushsubscriptionchange", (event) => {
  // A service worker has no page-held CSRF context and cannot read the
  // installation UUID in localStorage. Persist only a local
  // rotation marker and ask authenticated pages to reconcile on their next run.
  event.waitUntil(
    Promise.all([
      markPushRotationNeeded().catch(() => undefined),
      self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(
        (windowClients) => {
          for (const client of windowClients) {
            try {
              if (new URL(client.url).origin === self.location.origin) {
                client.postMessage({ type: "MADAR_PUSH_RECONCILE_REQUIRED" });
              }
            } catch {
              // Ignore malformed/non-window client URLs.
            }
          }
        },
      ),
    ]),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const action = normalizeNotificationAction(event.notification.data?.action);
  const targetUrl = new URL(action.path, self.location.origin).href;

  event.waitUntil((async () => {
    const windowClients = await self.clients.matchAll({
      type: "window",
      includeUncontrolled: true,
    });
    for (const client of windowClients) {
      try {
        if (new URL(client.url).origin !== self.location.origin) continue;
        if (typeof client.navigate === "function") await client.navigate(targetUrl);
        if (typeof client.focus === "function") return client.focus();
      } catch {
        // Try the next same-origin client, then fall back to a new window.
      }
    }
    return self.clients.openWindow(targetUrl);
  })());
});
