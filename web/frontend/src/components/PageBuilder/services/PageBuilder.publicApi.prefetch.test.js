import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));

vi.mock("../../../utils/apiClient", () => ({
  apiFetch: mocks.apiFetch,
  createApiError: (response, data) => Object.assign(new Error(data?.detail || "Request failed"), { status: response.status }),
  getApiUrl: (path) => `/api${path}`,
}));

const jsonResponse = (status, data) => ({
  ok: status >= 200 && status < 300,
  status,
  text: async () => JSON.stringify(data),
});

const flushMicrotasks = () => new Promise((resolve) => setTimeout(resolve, 0));

describe("early public runtime reads", () => {
  let api;

  beforeEach(async () => {
    vi.resetModules();
    mocks.apiFetch.mockReset();
    api = await import("./PageBuilder.publicApi");
  });

  afterEach(() => vi.useRealTimers());

  it("lets the runtime adopt the in-flight site read instead of requesting again", async () => {
    const payload = { site: { subdomain: "tenant-a" } };
    mocks.apiFetch.mockResolvedValue(jsonResponse(200, payload));

    api.prefetchPublicSiteRuntime("tenant-a");
    await expect(api.fetchPublicSiteRuntime("tenant-a")).resolves.toEqual(payload);

    expect(mocks.apiFetch).toHaveBeenCalledTimes(1);
    expect(mocks.apiFetch).toHaveBeenCalledWith("/api/public/sites/tenant-a/runtime", { method: "GET", cache: "no-store" });
  });

  it("issues the early form read exactly as the runtime would and adopts it once", async () => {
    mocks.apiFetch.mockResolvedValue(jsonResponse(200, { form: { id: "form_1" } }));

    api.prefetchPublicForm("tenant-a", "form_1");
    api.prefetchPublicForm("tenant-a", "form_1");
    await api.fetchPublicForm("tenant-a", "form_1");

    expect(mocks.apiFetch).toHaveBeenCalledTimes(1);
    expect(mocks.apiFetch).toHaveBeenCalledWith("/api/public/sites/tenant-a/forms/form_1", { method: "GET", cache: "no-store" });
  });

  it("shares one request with a StrictMode effect replay but never serves it as a cache", async () => {
    mocks.apiFetch.mockResolvedValue(jsonResponse(200, { site: {} }));

    api.prefetchPublicSiteRuntime("tenant-a");
    const first = api.fetchPublicSiteRuntime("tenant-a");
    const replay = api.fetchPublicSiteRuntime("tenant-a");
    expect(replay).toBe(first);
    await first;
    await flushMicrotasks();
    await api.fetchPublicSiteRuntime("tenant-a");

    expect(mocks.apiFetch).toHaveBeenCalledTimes(2);
  });

  it("never lets one tenant or form adopt another's early read", async () => {
    mocks.apiFetch.mockImplementation(async (url) => jsonResponse(200, { url }));

    api.prefetchPublicSiteRuntime("tenant-a");
    api.prefetchPublicForm("tenant-a", "form_1");
    await expect(api.fetchPublicSiteRuntime("tenant-b")).resolves.toEqual({ url: "/api/public/sites/tenant-b/runtime" });
    await expect(api.fetchPublicForm("tenant-b", "form_1")).resolves.toEqual({ url: "/api/public/sites/tenant-b/forms/form_1" });
    await expect(api.fetchPublicForm("tenant-a", "form_2")).resolves.toEqual({ url: "/api/public/sites/tenant-a/forms/form_2" });
    await expect(api.fetchPublicSiteRuntime("tenant-a")).resolves.toEqual({ url: "/api/public/sites/tenant-a/runtime" });

    expect(mocks.apiFetch).toHaveBeenCalledTimes(5);
  });

  it("hands an early failure to the runtime unchanged without an unhandled rejection", async () => {
    const unhandled = vi.fn();
    process.on("unhandledRejection", unhandled);
    mocks.apiFetch.mockResolvedValue(jsonResponse(404, { detail: "Published site not found" }));

    api.prefetchPublicSiteRuntime("missing-site");
    await flushMicrotasks();
    await flushMicrotasks();
    await expect(api.fetchPublicSiteRuntime("missing-site")).rejects.toMatchObject({ status: 404, message: "Published site not found" });
    await flushMicrotasks();

    process.off("unhandledRejection", unhandled);
    expect(unhandled).not.toHaveBeenCalled();
    expect(mocks.apiFetch).toHaveBeenCalledTimes(1);
  });

  it("discards an early read the runtime did not adopt promptly", async () => {
    vi.useFakeTimers();
    mocks.apiFetch.mockResolvedValue(jsonResponse(200, { site: {} }));

    api.prefetchPublicSiteRuntime("tenant-a");
    vi.advanceTimersByTime(10_001);
    await api.fetchPublicSiteRuntime("tenant-a");

    expect(mocks.apiFetch).toHaveBeenCalledTimes(2);
  });
});
