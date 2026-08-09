self.addEventListener("install", (event) => {
  // This worker owns no caches or in-flight application state, so activating
  // an update immediately cannot expose stale tenant or authenticated data.
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  try {
    const payload = event.data ? event.data.json() : {};
    const title = payload.title || "Madar";
    const options = {
      body: payload.body || "You have a new notification.",
      icon: "/pwa-icon-192.png",
      badge: "/pwa-icon-192.png",
      data: payload.data || {},
    };

    event.waitUntil(self.registration.showNotification(title, options));
  } catch {
    const payload = {
      title: "Madar",
      body: event.data ? event.data.text() : "",
    };
    const options = {
      body: payload.body || "You have a new notification.",
      icon: "/pwa-icon-192.png",
      badge: "/pwa-icon-192.png",
      data: payload.data || {},
    };

    event.waitUntil(self.registration.showNotification(payload.title, options));
  }
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const targetUrl = event.notification.data?.url || "/notifications";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ("focus" in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }

      return self.clients.openWindow(targetUrl);
    }),
  );
});
