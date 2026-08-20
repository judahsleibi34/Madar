import { beforeEach, describe, expect, it, vi } from "vitest";

const loadModule = async () => {
  vi.resetModules();
  return import("./serviceWorker");
};

describe("Madar service-worker registration", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("returns null in unsupported browsers", async () => {
    const { getMadarServiceWorkerRegistration } = await loadModule();
    await expect(getMadarServiceWorkerRegistration({})).resolves.toBeNull();
  });

  it("reuses an existing root registration", async () => {
    const existing = { scope: "https://example.test/" };
    const navigatorLike = {
      serviceWorker: {
        getRegistration: vi.fn().mockResolvedValue(existing),
        register: vi.fn(),
      },
    };
    const { getMadarServiceWorkerRegistration } = await loadModule();
    await expect(getMadarServiceWorkerRegistration(navigatorLike)).resolves.toBe(existing);
    expect(navigatorLike.serviceWorker.getRegistration).toHaveBeenCalledWith("/");
    expect(navigatorLike.serviceWorker.register).not.toHaveBeenCalled();
  });

  it("deduplicates concurrent registration callers without prompting or subscribing", async () => {
    const registration = { pushManager: { subscribe: vi.fn() } };
    const navigatorLike = {
      serviceWorker: {
        getRegistration: vi.fn().mockResolvedValue(null),
        register: vi.fn().mockResolvedValue(registration),
      },
    };
    const requestPermission = vi.fn();
    const { getMadarServiceWorkerRegistration } = await loadModule();
    const first = getMadarServiceWorkerRegistration(navigatorLike);
    const second = getMadarServiceWorkerRegistration(navigatorLike);

    await expect(Promise.all([first, second])).resolves.toEqual([
      registration,
      registration,
    ]);
    expect(navigatorLike.serviceWorker.register).toHaveBeenCalledTimes(1);
    expect(navigatorLike.serviceWorker.register).toHaveBeenCalledWith(
      "/madar-push-sw.js",
      { scope: "/" }
    );
    expect(requestPermission).not.toHaveBeenCalled();
    expect(registration.pushManager.subscribe).not.toHaveBeenCalled();
  });

  it("allows a later retry after registration failure", async () => {
    const registration = { scope: "https://example.test/" };
    const navigatorLike = {
      serviceWorker: {
        getRegistration: vi.fn().mockResolvedValue(null),
        register: vi
          .fn()
          .mockRejectedValueOnce(new Error("worker unavailable"))
          .mockResolvedValueOnce(registration),
      },
    };
    const { getMadarServiceWorkerRegistration } = await loadModule();
    await expect(getMadarServiceWorkerRegistration(navigatorLike)).rejects.toThrow(
      "worker unavailable"
    );
    await expect(getMadarServiceWorkerRegistration(navigatorLike)).resolves.toBe(registration);
    expect(navigatorLike.serviceWorker.register).toHaveBeenCalledTimes(2);
  });

  it("reads an existing Push endpoint without registering or prompting", async () => {
    const getSubscription = vi.fn().mockResolvedValue({ endpoint: "https://push.example/device" });
    const navigatorLike = {
      serviceWorker: {
        getRegistration: vi.fn().mockResolvedValue({ pushManager: { getSubscription } }),
        register: vi.fn(),
      },
    };
    const { getExistingMadarPushEndpoint } = await loadModule();
    await expect(getExistingMadarPushEndpoint(navigatorLike)).resolves.toBe(
      "https://push.example/device"
    );
    expect(navigatorLike.serviceWorker.register).not.toHaveBeenCalled();
    expect(getSubscription).toHaveBeenCalledTimes(1);
  });
});
