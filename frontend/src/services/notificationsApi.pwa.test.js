import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetch, getMadarServiceWorkerRegistration } = vi.hoisted(() => ({
  apiFetch: vi.fn(),
  getMadarServiceWorkerRegistration: vi.fn(),
}));

vi.mock("../pwa/serviceWorker", () => ({
  getMadarServiceWorkerRegistration,
}));

vi.mock("../utils/apiClient", () => ({
  apiFetch,
  getApiUrl: (path) => path,
  readApiError: (_data, fallback) => fallback,
  readApiResponse: async (response) => response.data,
}));

import { enableBrowserPushNotifications } from "./notificationsApi";

describe("explicit browser Push enablement", () => {
  beforeEach(() => {
    vi.clearAllMocks();
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
      value: { requestPermission: vi.fn().mockResolvedValue("granted") },
    });
    apiFetch.mockImplementation(async (url) => ({
      ok: true,
      data: url.includes("push-public-key")
        ? { enabled: true, public_key: "AQID" }
        : { success: true },
    }));
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
    expect(getMadarServiceWorkerRegistration).toHaveBeenCalledTimes(1);
    expect(subscribe).not.toHaveBeenCalled();
    expect(apiFetch).toHaveBeenCalledWith(
      "/notifications/push-subscriptions",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("does not register or subscribe after permission denial", async () => {
    window.Notification.requestPermission.mockResolvedValue("denied");
    await expect(enableBrowserPushNotifications()).resolves.toEqual({
      enabled: false,
      reason: "permission_denied",
    });
    expect(getMadarServiceWorkerRegistration).not.toHaveBeenCalled();
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
});
