self.addEventListener("push", (event) => {
  try {
    const payload = event.data ? event.data.json() : {};
    const title = payload.title || "Madar";
    const options = {
      body: payload.body || "You have a new notification.",
      icon: "/favicon.svg",
      badge: "/favicon.svg",
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
      icon: "/favicon.svg",
      badge: "/favicon.svg",
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
