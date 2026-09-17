import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearEcommerceCatalogCache,
  getOrCreateEcommerceCatalogRequest,
  readEcommerceCatalogCache,
  readEcommerceCatalogCacheSnapshot,
  readEcommerceThemeCache,
  removeFromEcommerceCatalogCache,
  updateEcommerceCatalogCache,
  writeEcommerceCatalogCache,
  writeEcommerceThemeCache,
} from "./ecommerceCatalogCache";

const catalog = (name) => ({
  tags: [{ id: `${name}-tag` }],
  categories: [{ id: `${name}-category` }],
  products: [{ id: `${name}-product` }],
});

afterEach(() => {
  vi.useRealTimers();
});

beforeEach(() => {
  window.sessionStorage.clear();
  clearEcommerceCatalogCache("user-1");
  clearEcommerceCatalogCache("user-2");
});

describe("Ecommerce catalog cache", () => {
  it("isolates cached catalogs by authenticated user scope", () => {
    writeEcommerceCatalogCache("user-1", catalog("first"));
    writeEcommerceCatalogCache("user-2", catalog("second"));

    expect(readEcommerceCatalogCache("user-1").products[0].id).toBe("first-product");
    expect(readEcommerceCatalogCache("user-2").products[0].id).toBe("second-product");

    clearEcommerceCatalogCache("user-1");
    expect(readEcommerceCatalogCache("user-1")).toBeNull();
    expect(readEcommerceCatalogCache("user-2")).toBeTruthy();
  });

  it("keeps stale data available while a quiet refresh runs", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-21T00:00:00Z"));
    writeEcommerceCatalogCache("user-1", catalog("cached"));

    vi.setSystemTime(new Date("2026-08-21T00:04:00Z"));

    expect(readEcommerceCatalogCache("user-1")).toBeNull();
    expect(readEcommerceCatalogCacheSnapshot("user-1")).toMatchObject({
      catalog: catalog("cached"),
      isStale: true,
    });
  });

  it("deduplicates simultaneous catalog requests", async () => {
    const loader = vi.fn(async () => catalog("shared"));

    const first = getOrCreateEcommerceCatalogRequest("user-1", loader);
    const second = getOrCreateEcommerceCatalogRequest("user-1", loader);

    expect(first).toBe(second);
    await expect(first).resolves.toEqual(catalog("shared"));
    expect(loader).toHaveBeenCalledOnce();
  });
  it("updates cached records without reloading the whole catalog", () => {
    writeEcommerceCatalogCache("user-1", catalog("original"));
    updateEcommerceCatalogCache("user-1", "products", { id: "original-product", name: "Updated" });
    expect(readEcommerceCatalogCache("user-1").products).toEqual([{ id: "original-product", name: "Updated" }]);

    removeFromEcommerceCatalogCache("user-1", "products", "original-product");
    expect(readEcommerceCatalogCache("user-1").products).toEqual([]);
  });

  it("caches store theme settings by user scope", () => {
    const theme = { accent: "#111111", background: "#ffffff", surface: "#eeeeee", text: "#222222", muted: "#777777" };
    writeEcommerceThemeCache("user-1", theme);
    expect(readEcommerceThemeCache("user-1")).toEqual(theme);
    expect(readEcommerceThemeCache("user-2")).toBeNull();
  });
});
