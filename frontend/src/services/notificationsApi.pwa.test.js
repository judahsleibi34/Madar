import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetch, clearPushRotationNeeded, getExistingMadarPushEndpoint, getMadarServiceWorkerRegistration, readPushRotationNeeded } = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  clearPushRotationNeeded: vi.fn().mockResolvedValue(true),
  getExistingMadarPushEndpoint: vi.fn().mockResolvedValue(null),
  getMadarServiceWorkerRegistration: vi.fn(),
  readPushRotationNeeded: vi.fn().mockResolvedValue(false),
}));

vi.mock("../pwa/serviceWorker", () => ({
  getExistingMadarPushEndpoint,
  getMadarServiceWorkerRegistration,
}));

vi.mock("../pwa/pushLifecycle", () => ({
  clearPushRotationNeeded,
  readPushRotationNeeded,
}));

vi.mock("../utils/apiClient", () => ({
  apiFetch,
  getApiUrl: (path) => path,
  readApiError: (_data, fallback) => fallback,
  readApiResponse: async (response) => response.data,
}));

import {
  enableBrowserPushNotifications,
  getBrowserPushStatus,
  reconcileBrowserPushLifecycle,
} from "./notificationsApi";

describe("explicit browser Push enablement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(navigator, "userAgent", {
      configurable: true,
      value: "Mozilla/5.0 (Windows NT 10.0)",
    });
    Object.defineProperty(navigator, "standalone", {
      configurable: true,
      value: false,
    });
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: {},
    });
    Object.defineProperty(window, "PushManager", {
      configurable: true,
      value: function PushManager() {},
    });
    Object.defineProperty(window, "Notification", {
      configurable: true,
      value: {
        permission: "default",
        requestPermission: vi.fn().mockResolvedValue("granted"),
      },
    });
    apiFetch.mockImplementation(async (url) => ({
      ok: true,
      data: url.includes("push-public-key")
        ? { enabled: true, public_key: "AQID" }
        : { success: true },
    }));
  });

  it("guides iPhone Safari users to install the Home Screen app before requesting Push", async () => {
    Object.defineProperty(navigator, "userAgent", {
      configurable: true,
      value: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)",
    });

    await expect(enableBrowserPushNotifications()).resolves.toEqual({
      enabled: false,
      reason: "ios_home_screen_required",
    });
    expect(window.Notification.requestPermission).not.toHaveBeenCalled();
    expect(getMadarServiceWorkerRegistration).not.toHaveBeenCalled();
  });

  it("gives Android users a supported-browser message when Push APIs are absent", async () => {
    Object.defineProperty(navigator, "userAgent", {
      configurable: true,
      value: "Mozilla/5.0 (Linux; Android 15; Pixel 9)",
    });
    Reflect.deleteProperty(window, "PushManager");

    await expect(enableBrowserPushNotifications()).resolves.toEqual({
      enabled: false,
      reason: "android_browser_unsupported",
    });
    expect(window.Notification.requestPermission).not.toHaveBeenCalled();
  });

  it("requests permission only in the explicit flow and reuses the central registration", async () => {
    const subscription = { toJSON: () => ({ endpoint: "https://push.example/sub" }) };
    const subscribe = vi.fn();
    getMadarServiceWorkerRegistration.mockResolvedValue({
      pushManager: {
        getSubscription: vi.fn().mockResolvedValue(subscription),
        subscribe,
      },
    });

    await expect(enableBrowserPushNotifications()).resolves.toEqual({ enabled: true });
    expect(window.Notification.requestPermission).toHaveBeenCalledTimes(1);
    expect(window.Notification.requestPermission.mock.invocationCallOrder[0]).toBeLessThan(
      apiFetch.mock.invocationCallOrder[0]
    );
    expect(getMadarServiceWorkerRegistration).toHaveBeenCalledTimes(1);
    expect(subscribe).not.toHaveBeenCalled();
    expect(apiFetch).toHaveBeenCalledWith(
      "/notifications/push-subscriptions",
      expect.objectContaining({ method: "POST" })
    );
    expect(clearPushRotationNeeded).toHaveBeenCalled();
  });

  it("does not register or subscribe after permission denial", async () => {
    window.Notification.requestPermission.mockResolvedValue("denied");
    await expect(enableBrowserPushNotifications()).resolves.toEqual({
      enabled: false,
      reason: "permission_denied",
    });
    expect(getMadarServiceWorkerRegistration).not.toHaveBeenCalled();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("does not ask Apple for permission when preloaded server configuration is unavailable", async () => {
    await expect(enableBrowserPushNotifications({
      pushConfig: { enabled: false, public_key: "" },
    })).resolves.toEqual({
      enabled: false,
      reason: "server_not_configured",
    });
    expect(window.Notification.requestPermission).not.toHaveBeenCalled();
    expect(getMadarServiceWorkerRegistration).not.toHaveBeenCalled();
  });

  it("restores enabled state from the browser permission and saved subscription", async () => {
    window.Notification.permission = "granted";
    getExistingMadarPushEndpoint.mockResolvedValue("https://push.example/ios-device");
    await expect(getBrowserPushStatus()).resolves.toEqual({ enabled: true });
  });

  it("explains that Web Push requires a secure origin", async () => {
    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: false,
    });
    await expect(enableBrowserPushNotifications()).resolves.toEqual({
      enabled: false,
      reason: "secure_context_required",
    });
    expect(window.Notification.requestPermission).not.toHaveBeenCalled();
    Object.defineProperty(window, "isSecureContext", {
      configurable: true,
      value: true,
    });
  });

  it("reconciles an installation before binding Push when tenant context is available", async () => {
    const subscription = {
      toJSON: () => ({
        endpoint: "https://push.example/sub",
        keys: { p256dh: "A", auth: "B" },
      }),
    };
    getMadarServiceWorkerRegistration.mockResolvedValue({
      pushManager: {
        getSubscription: vi.fn().mockResolvedValue(subscription),
        subscribe: vi.fn(),
      },
    });

    await expect(enableBrowserPushNotifications({ tenantId: 7 })).resolves.toEqual({ enabled: true });
    const installationCall = apiFetch.mock.calls.find(([url]) => url === "/installations/register");
    const subscriptionCall = apiFetch.mock.calls.find(([url]) => url === "/notifications/push-subscriptions");
    expect(installationCall).toBeTruthy();
    expect(subscriptionCall).toBeTruthy();
    expect(JSON.parse(subscriptionCall[1].body).installation_id).toMatch(
      /^[0-9a-f-]{36}$/i
    );
    expect(apiFetch.mock.calls.indexOf(installationCall)).toBeLessThan(
      apiFetch.mock.calls.indexOf(subscriptionCall)
    );
  });

  it("reconciles an existing subscription without prompting", async () => {
    window.Notification.permission = "granted";
    const subscription = {
      toJSON: () => ({
        endpoint: "https://push.example/sub",
        keys: { p256dh: "A", auth: "B" },
      }),
    };
    const subscribe = vi.fn();
    getMadarServiceWorkerRegistration.mockResolvedValue({
      pushManager: {
        getSubscription: vi.fn().mockResolvedValue(subscription),
        subscribe,
      },
    });

    await expect(reconcileBrowserPushLifecycle({
      installation: {
        installationId: "123e4567-e89b-42d3-a456-426614174000",
        installation: { notifications_enabled: true },
      },
    })).resolves.toEqual({ reconciled: true, restored: true });
    expect(window.Notification.requestPermission).not.toHaveBeenCalled();
    expect(subscribe).not.toHaveBeenCalled();
    expect(apiFetch).toHaveBeenCalledWith(
      "/notifications/push-subscriptions",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("restores a missing subscription only after prior explicit opt-in", async () => {
    window.Notification.permission = "granted";
    const subscription = {
      toJSON: () => ({ endpoint: "https://push.example/restored", keys: { p256dh: "A", auth: "B" } }),
    };
    const subscribe = vi.fn().mockResolvedValue(subscription);
    getMadarServiceWorkerRegistration.mockResolvedValue({
      pushManager: {
        getSubscription: vi.fn().mockResolvedValue(null),
        subscribe,
      },
    });

    await expect(reconcileBrowserPushLifecycle({
      installation: {
        installationId: "123e4567-e89b-42d3-a456-426614174000",
        installation: { notifications_enabled: true },
      },
    })).resolves.toEqual({ reconciled: true, restored: true });
    expect(subscribe).toHaveBeenCalledTimes(1);
    expect(window.Notification.requestPermission).not.toHaveBeenCalled();
  });

  it("does not create Push from permission alone without explicit opt-in", async () => {
    window.Notification.permission = "granted";
    const subscribe = vi.fn();
    getMadarServiceWorkerRegistration.mockResolvedValue({
      pushManager: {
        getSubscription: vi.fn().mockResolvedValue(null),
        subscribe,
      },
    });

    await expect(reconcileBrowserPushLifecycle({
      installation: {
        installationId: "123e4567-e89b-42d3-a456-426614174000",
        installation: { notifications_enabled: false },
      },
    })).resolves.toEqual({ reconciled: false, reason: "subscription_missing" });
    expect(subscribe).not.toHaveBeenCalled();
    expect(window.Notification.requestPermission).not.toHaveBeenCalled();
  });

  it.each(["default", "denied"])(
    "does not bind, subscribe, or prompt when permission is %s",
    async (permission) => {
      window.Notification.permission = permission;
      const subscribe = vi.fn();
      getMadarServiceWorkerRegistration.mockResolvedValue({
        pushManager: { getSubscription: vi.fn(), subscribe },
      });

      await expect(reconcileBrowserPushLifecycle({
        installation: {
          installationId: "123e4567-e89b-42d3-a456-426614174000",
          installation: { notifications_enabled: true },
        },
      })).resolves.toEqual({ reconciled: false, reason: permission });
      expect(getMadarServiceWorkerRegistration).not.toHaveBeenCalled();
      expect(subscribe).not.toHaveBeenCalled();
      expect(window.Notification.requestPermission).not.toHaveBeenCalled();
    }
  );

  it("revokes the current browser endpoint after permission is denied", async () => {
    window.Notification.permission = "denied";
    getExistingMadarPushEndpoint.mockResolvedValue("https://push.example/current-device");

    await expect(reconcileBrowserPushLifecycle()).resolves.toEqual({
      reconciled: false,
      reason: "denied",
    });
    expect(apiFetch).toHaveBeenCalledWith(
      "/notifications/push-subscriptions",
      expect.objectContaining({
        method: "DELETE",
        body: JSON.stringify({ endpoint: "https://push.example/current-device" }),
      })
    );
    expect(getMadarServiceWorkerRegistration).not.toHaveBeenCalled();
    expect(window.Notification.requestPermission).not.toHaveBeenCalled();
  });
});
