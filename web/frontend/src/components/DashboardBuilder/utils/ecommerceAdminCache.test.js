import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearEcommerceAdminCache,
  getEcommerceCacheScope,
  readEcommerceAdminCacheSnapshot,
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


it("does not restore invalidated data when an older request finishes", async () => {
  let finish;
  const pending = loadEcommerceAdminResource("tenant-a", "orders", () => new Promise(resolve => { finish = resolve; }));
  await Promise.resolve();
  clearEcommerceAdminCache("tenant-a", "orders");
  await loadEcommerceAdminResource("tenant-a", "orders", async () => ({orders:["new"]}));
  finish({orders:["old"]});
  await pending;
  expect(readEcommerceAdminCache("tenant-a", "orders")).toEqual({orders:["new"]});
});

it("retains stale snapshots while refreshing after 30 seconds", async () => {
  vi.useFakeTimers();
  vi.setSystemTime(100_000);
  const loader = vi.fn().mockResolvedValue({ areas: ["saved"] });
  await loadEcommerceAdminResource("tenant-a", "delivery", loader);
  await loadEcommerceAdminResource("tenant-a", "delivery", loader);
  expect(loader).toHaveBeenCalledOnce();
  vi.setSystemTime(131_000);
  expect(readEcommerceAdminCache("tenant-a", "delivery")).toBeNull();
  expect(readEcommerceAdminCacheSnapshot("tenant-a", "delivery")).toMatchObject({ data:{areas:["saved"]}, isStale:true });
  await expect(loadEcommerceAdminResource("tenant-a", "delivery", async () => { throw new Error("Unavailable"); })).rejects.toThrow("Unavailable");
  expect(readEcommerceAdminCacheSnapshot("tenant-a", "delivery")?.data).toEqual({ areas:["saved"] });
});

it("restores cached resources after a module reload and clears persisted snapshots", async () => {
  await loadEcommerceAdminResource("tenant-a", "loyalty", async () => ({rule:{enabled:true}}));
  vi.resetModules();
  const reloaded = await import("./ecommerceAdminCache");
  const loader=vi.fn();
  expect(await reloaded.loadEcommerceAdminResource("tenant-a", "loyalty", loader)).toEqual({rule:{enabled:true}});
  expect(loader).not.toHaveBeenCalled();
  reloaded.clearEcommerceAdminCache();
  expect(reloaded.readEcommerceAdminCacheSnapshot("tenant-a", "loyalty")).toBeNull();
  expect(JSON.parse(sessionStorage.getItem("madar-ecommerce-admin-cache-v1"))).toEqual({});
});

it("uses separate scopes for different users in the same tenant", () => {
  expect(getEcommerceCacheScope({id:1,tenant_id:7})).not.toBe(getEcommerceCacheScope({id:2,tenant_id:7}));
  expect(getEcommerceCacheScope({id:1,tenant_id:7})).not.toBe(getEcommerceCacheScope({id:1,tenant_id:8}));
});
