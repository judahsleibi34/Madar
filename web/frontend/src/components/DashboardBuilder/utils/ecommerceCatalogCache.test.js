import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearEcommerceCatalogCache,
  getOrCreateEcommerceCatalogRequest,
  readEcommerceCatalogCache,
  writeEcommerceCatalogCache,
} from "./ecommerceCatalogCache";

const catalog = (name) => ({
  tags: [{ id: `${name}-tag` }],
  categories: [{ id: `${name}-category` }],
  products: [{ id: `${name}-product` }],
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

  it("deduplicates simultaneous catalog requests", async () => {
    const loader = vi.fn(async () => catalog("shared"));

    const first = getOrCreateEcommerceCatalogRequest("user-1", loader);
    const second = getOrCreateEcommerceCatalogRequest("user-1", loader);

    expect(first).toBe(second);
    await expect(first).resolves.toEqual(catalog("shared"));
    expect(loader).toHaveBeenCalledOnce();
  });
});
