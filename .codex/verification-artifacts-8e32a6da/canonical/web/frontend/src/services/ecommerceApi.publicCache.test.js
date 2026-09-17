import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ apiFetch: vi.fn() }));

vi.mock("../utils/apiClient", () => ({
  apiFetch: mocks.apiFetch,
  getApiUrl: (path) => path,
  readApiResponse: (response) => response.json(),
  readApiError: (_data, fallback) => fallback,
}));

const response = (data) => ({
  ok: true,
  status: 200,
  json: async () => data,
});

describe("public ecommerce catalog cache", () => {
  beforeEach(() => {
    vi.resetModules();
    mocks.apiFetch.mockReset();
    window.sessionStorage.clear();
  });

  it("restores a fresh catalog from session cache after the module reloads", async () => {
    const payload = {
      site: { brand: "Form & Flow" },
      catalog: { products: [{ id: "mat", images: ["/form-flow-products/reformer-mat-towel.jpg"] }] },
    };
    mocks.apiFetch.mockResolvedValue(response(payload));

    let ecommerceApi = await import("./ecommerceApi");
    const first = await ecommerceApi.fetchPublicEcommerceCatalog("madar-demo", {
      sort: "latest",
      page: "1",
      locale: "en",
      limit: "12",
    });
    expect(first).toEqual(payload);
    expect(mocks.apiFetch).toHaveBeenCalledTimes(1);
    expect(window.sessionStorage.getItem("madar-public-store-cache-v2")).toContain("reformer-mat-towel.jpg");

    vi.resetModules();
    ecommerceApi = await import("./ecommerceApi");
    const restored = await ecommerceApi.fetchPublicEcommerceCatalog("madar-demo", {
      sort: "latest",
      page: "1",
      locale: "en",
      limit: "12",
    });
    expect(restored).toEqual(payload);
    expect(mocks.apiFetch).toHaveBeenCalledTimes(1);
  });

  it("clears both memory and persisted public catalog entries", async () => {
    mocks.apiFetch.mockResolvedValue(response({ site: {}, catalog: { products: [] } }));
    const ecommerceApi = await import("./ecommerceApi");
    await ecommerceApi.preloadPublicEcommerceCatalog("madar-demo");
    expect(window.sessionStorage.getItem("madar-public-store-cache-v2")).not.toBeNull();
    ecommerceApi.clearPublicEcommerceCache();
    expect(window.sessionStorage.getItem("madar-public-store-cache-v2")).toBeNull();
  });
});
