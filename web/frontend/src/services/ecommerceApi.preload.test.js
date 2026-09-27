import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));

vi.mock("../utils/apiClient", () => ({
  apiFetch: mocks.apiFetch,
  createApiError: (response, _data, message) => Object.assign(new Error(message), { status: response.status }),
  getApiUrl: (path) => path,
  readApiResponse: (response) => response.json(),
  readApiError: (_data, fallback) => fallback,
}));

const response = (status, data) => ({
  ok: status >= 200 && status < 300,
  status,
  headers: { get: () => "application/json" },
  json: async () => data,
});

describe("catalog options hard-navigation preload", () => {
  beforeEach(() => {
    vi.resetModules();
    mocks.apiFetch.mockReset();
    window.sessionStorage.clear();
  });

  it("reuses one independently authorized speculative read", async () => {
    const payload = { tags: [], categories: [], brands: [], commerce_currency: "ILS" };
    mocks.apiFetch.mockResolvedValue(response(200, payload));
    const api = await import("./ecommerceApi");

    await api.preloadEcommerceCatalogOptions();
    await expect(api.fetchEcommerceCatalogOptions({ scope: "tenant:7", force: true })).resolves.toEqual(payload);

    expect(mocks.apiFetch).toHaveBeenCalledTimes(1);
    expect(mocks.apiFetch.mock.calls[0][1]).toMatchObject({ skipAuthRefresh: true });
  });

  it("defers session refresh until the protected route consumes a provisional 401", async () => {
    const payload = { tags: [], categories: [], brands: [], commerce_currency: "ILS" };
    mocks.apiFetch
      .mockResolvedValueOnce(response(401, { detail: "Invalid or expired session" }))
      .mockResolvedValueOnce(response(200, payload));
    const api = await import("./ecommerceApi");

    await expect(api.preloadEcommerceCatalogOptions()).rejects.toMatchObject({ status: 401 });
    await expect(api.fetchEcommerceCatalogOptions({ scope: "tenant:7", force: true })).resolves.toEqual(payload);

    expect(mocks.apiFetch).toHaveBeenCalledTimes(2);
    expect(mocks.apiFetch.mock.calls[0][1]).toMatchObject({ skipAuthRefresh: true });
    expect(mocks.apiFetch.mock.calls[1][1]).not.toHaveProperty("skipAuthRefresh");
  });

  it("drops speculative data on logout before it can enter a tenant-scoped cache", async () => {
    const first = { commerce_currency: "ILS" };
    const second = { commerce_currency: "USD" };
    mocks.apiFetch
      .mockResolvedValueOnce(response(200, first))
      .mockResolvedValueOnce(response(200, second));
    const api = await import("./ecommerceApi");

    await api.preloadEcommerceCatalogOptions();
    api.clearEcommerceCatalogOptionsPreload();
    await expect(api.fetchEcommerceCatalogOptions({ scope: "tenant:8", force: true })).resolves.toEqual(second);

    expect(mocks.apiFetch).toHaveBeenCalledTimes(2);
  });
});
