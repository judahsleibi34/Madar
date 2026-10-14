import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  prefetchPublicSiteRuntime: vi.fn(),
  prefetchPublicForm: vi.fn(),
  fetchPublicEcommerceCatalog: vi.fn(() => Promise.resolve({})),
  fetchPublicEcommerceProduct: vi.fn(() => Promise.resolve({})),
  fetchPublicEcommerceProfile: vi.fn(() => Promise.resolve({})),
}));

vi.mock("./components/PageBuilder/services/PageBuilder.publicApi", () => ({
  prefetchPublicSiteRuntime: mocks.prefetchPublicSiteRuntime,
  prefetchPublicForm: mocks.prefetchPublicForm,
}));
vi.mock("./services/ecommerceApi", () => ({
  fetchPublicEcommerceCatalog: mocks.fetchPublicEcommerceCatalog,
  fetchPublicEcommerceProduct: mocks.fetchPublicEcommerceProduct,
  fetchPublicEcommerceProfile: mocks.fetchPublicEcommerceProfile,
}));
vi.mock("./components/PageBuilder/runtime/TenantSiteRuntime", () => ({ default: () => null }));
vi.mock("./components/EcommerceStore/EcommerceStorefront", () => ({ default: () => null }));

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));
const at = (url) => {
  const parsed = new URL(url);
  return { hostname: parsed.hostname, pathname: parsed.pathname, search: parsed.search };
};

describe("hosted tenant runtime detection", () => {
  it.each([
    ["https://store-a.madarportal.com/", { tenant: "store-a", kind: "site" }],
    ["https://store-a.madarportal.com/about/team", { tenant: "store-a", kind: "site" }],
    ["https://store-a.madarportal.com/forms/form_1", { tenant: "store-a", kind: "form", formSegment: "form_1" }],
    ["https://store-a.madarportal.com/forms/form_1/", { tenant: "store-a", kind: "form", formSegment: "form_1" }],
    ["https://store-a.madarportal.com/forms/form_1/extra", { tenant: "store-a", kind: "site" }],
    ["https://store-a.madarportal.com/shop", { tenant: "store-a", kind: "store", routeTail: "", search: "" }],
    ["https://store-a.madarportal.com/shop/catalog?tag=new", { tenant: "store-a", kind: "store", routeTail: "catalog", search: "?tag=new" }],
    ["https://store-a.madarportal.com/SHOP/product/tee", { tenant: "store-a", kind: "store", routeTail: "product/tee", search: "" }],
    ["https://store-a.madarportal.com/shopping", { tenant: "store-a", kind: "site" }],
  ])("maps %s to the route the tenant router renders", async (url, expected) => {
    const { detectHostedTenantRuntime } = await import("./tenantRuntimePreload");
    expect(detectHostedTenantRuntime(at(url))).toEqual(expected);
  });

  it.each([
    "https://madarportal.com/shop",
    "https://www.madarportal.com/",
    "https://store-a.madarportal.com/academy/courses",
    "https://store-a.madarportal.com/my-learning",
  ])("does not preload %s", async (url) => {
    const { detectHostedTenantRuntime } = await import("./tenantRuntimePreload");
    expect(detectHostedTenantRuntime(at(url))).toBeNull();
  });
});

describe("hosted tenant preload", () => {
  beforeEach(() => {
    vi.resetModules();
    Object.values(mocks).forEach((mock) => mock.mockClear());
    window.localStorage.clear();
  });

  it("starts the site route chunk and runtime read for a site page", async () => {
    const preload = await import("./tenantRuntimePreload");
    preload.startHostedTenantPreload(at("https://store-a.madarportal.com/about"));
    await flush();

    expect(mocks.prefetchPublicSiteRuntime).toHaveBeenCalledTimes(1);
    expect(mocks.prefetchPublicSiteRuntime).toHaveBeenCalledWith("store-a");
    expect(mocks.prefetchPublicForm).not.toHaveBeenCalled();
    expect(preload.getLoadedTenantRouteModule("site")).toBeTruthy();
    expect(preload.getLoadedTenantRouteModule("store")).toBeNull();
  });

  it("starts the form read for a plain form id and skips ids that need decoding", async () => {
    const preload = await import("./tenantRuntimePreload");
    preload.startHostedTenantPreload(at("https://store-a.madarportal.com/forms/form_1"));
    preload.startHostedTenantPreload(at("https://store-a.madarportal.com/forms/form%201"));
    await flush();

    expect(mocks.prefetchPublicForm).toHaveBeenCalledTimes(1);
    expect(mocks.prefetchPublicForm).toHaveBeenCalledWith("store-a", "form_1");
    expect(mocks.prefetchPublicSiteRuntime).not.toHaveBeenCalled();
  });

  it("skips the site read when the runtime would normalize the subdomain differently", async () => {
    const preload = await import("./tenantRuntimePreload");
    preload.startHostedTenantPreload(at("https://store--a.madarportal.com/"));
    await flush();
    expect(mocks.prefetchPublicSiteRuntime).not.toHaveBeenCalled();
  });

  it("requests the storefront's exact primary catalog entry in the stored language", async () => {
    const preload = await import("./tenantRuntimePreload");
    const { getStorefrontPrimaryRequest } = await import("./components/EcommerceStore/storefrontPrimaryRequest");
    window.localStorage.setItem("madar.language", "ar");
    preload.startHostedTenantPreload(at("https://store-a.madarportal.com/shop/catalog?tag=new&page=2"));
    await flush();

    const expected = getStorefrontPrimaryRequest({ routeTail: "catalog", search: "?tag=new&page=2", locale: "ar" });
    expect(mocks.fetchPublicEcommerceCatalog).toHaveBeenCalledTimes(1);
    expect(mocks.fetchPublicEcommerceCatalog).toHaveBeenCalledWith("store-a", expected.filters);
    expect(Object.keys(mocks.fetchPublicEcommerceCatalog.mock.calls[0][1])).toEqual(
      ["search", "category", "brand", "tag", "min_price", "max_price", "sort", "page", "locale", "limit"],
    );
    expect(preload.getLoadedTenantRouteModule("store")).toBeTruthy();
    expect(preload.getLoadedTenantRouteModule("site")).toBeNull();
  });

  it("prefetches product and profile reads but leaves order confirmations to the storefront", async () => {
    const preload = await import("./tenantRuntimePreload");
    preload.startHostedTenantPreload(at("https://store-a.madarportal.com/shop/product/linen-shirt"));
    await vi.waitFor(() => expect(mocks.fetchPublicEcommerceProduct).toHaveBeenCalledWith("store-a", "linen-shirt", "en"));
    preload.startHostedTenantPreload(at("https://store-a.madarportal.com/shop/contact"));
    await vi.waitFor(() => expect(mocks.fetchPublicEcommerceProfile).toHaveBeenCalledWith("store-a"));
    preload.startHostedTenantPreload(at(`https://store-a.madarportal.com/shop/confirmation/${"a".repeat(64)}`));
    await flush();

    expect(mocks.fetchPublicEcommerceProduct).toHaveBeenCalledTimes(1);
    expect(mocks.fetchPublicEcommerceProfile).toHaveBeenCalledTimes(1);
    expect(mocks.fetchPublicEcommerceCatalog).not.toHaveBeenCalled();
  });


  it.each([null, "en", "ar", "AR", "ar-SA", "fr", ""])(
    "derives the same storefront locale as i18n for stored language %s",
    async (stored) => {
      const { getStoredLanguage } = await import("./i18n");
      const { normalizeCommerceLocale } = await import("./utils/commerceI18n");
      const preload = await import("./tenantRuntimePreload");
      if (stored !== null) window.localStorage.setItem("madar.language", stored);
      preload.startHostedTenantPreload(at("https://store-a.madarportal.com/shop"));
      await flush();

      const storage = { value: stored, getItem() { return this.value; }, setItem() {} };
      const expected = normalizeCommerceLocale(getStoredLanguage(storage));
      expect(mocks.fetchPublicEcommerceCatalog.mock.calls[0][1].locale).toBe(expected);
    },
  );
});
