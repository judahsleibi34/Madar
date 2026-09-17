import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearEcommerceAdminCache,
  loadEcommerceAdminResource,
  readEcommerceAdminCache,
} from "./ecommerceAdminCache";

beforeEach(() => {
  vi.useRealTimers();
  clearEcommerceAdminCache();
});

describe("ecommerce admin cache", () => {
  it("isolates data by authenticated scope", async () => {
    await loadEcommerceAdminResource("tenant-a", "orders", async () => ({ orders: ["a"] }));
    await loadEcommerceAdminResource("tenant-b", "orders", async () => ({ orders: ["b"] }));
    expect(readEcommerceAdminCache("tenant-a", "orders")).toEqual({ orders: ["a"] });
    expect(readEcommerceAdminCache("tenant-b", "orders")).toEqual({ orders: ["b"] });
  });

  it("deduplicates simultaneous requests", async () => {
    const loader = vi.fn(async () => ({ areas: [] }));
    const first = loadEcommerceAdminResource("tenant-a", "delivery", loader);
    const second = loadEcommerceAdminResource("tenant-a", "delivery", loader);
    expect(first).toBe(second);
    await first;
    expect(loader).toHaveBeenCalledOnce();
  });

  it("expires entries and supports mutation invalidation", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-14T00:00:00Z"));
    await loadEcommerceAdminResource("tenant-a", "loyalty", async () => ({ enabled: true }));
    vi.setSystemTime(new Date("2026-09-14T00:01:00Z"));
    expect(readEcommerceAdminCache("tenant-a", "loyalty")).toBeNull();
    await loadEcommerceAdminResource("tenant-a", "orders?page=1", async () => ({ orders: [] }));
    clearEcommerceAdminCache("tenant-a", "orders");
    expect(readEcommerceAdminCache("tenant-a", "orders?page=1")).toBeNull();
  });
});
