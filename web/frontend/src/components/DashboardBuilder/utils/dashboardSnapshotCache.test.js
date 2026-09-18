import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  fetchDashboardMetricsCached,
  clearAllDashboardSnapshotCaches,
  getDashboardCacheScope,
  readDashboardMetricsCache,
  readScreenTimeCache,
  writeDashboardMetricsCache,
  writeScreenTimeCache,
} from "./dashboardSnapshotCache";

beforeEach(() => { vi.restoreAllMocks(); clearAllDashboardSnapshotCaches(); window.sessionStorage.clear(); });

describe("dashboard snapshot cache", () => {

  it("isolates metrics by tenant and authenticated user", () => {
    const tenantA = getDashboardCacheScope({ id: 7, tenant_id: "a" });
    const tenantB = getDashboardCacheScope({ id: 7, tenant_id: "b" });
    writeDashboardMetricsCache(tenantA, { forms: 4 });

    expect(readDashboardMetricsCache(tenantA)).toEqual({ forms: 4 });
    expect(readDashboardMetricsCache(tenantB)).toBeNull();
  });

  it("keeps each screen-time period in a separate project cache", () => {
    const scope = getDashboardCacheScope({ id: 7, tenant_id: "a" });
    writeScreenTimeCache(scope, "project-1", "week", { total_seconds: 60 });
    writeScreenTimeCache(scope, "project-1", "month", { total_seconds: 180 });

    expect(readScreenTimeCache(scope, "project-1", "week")?.total_seconds).toBe(60);
    expect(readScreenTimeCache(scope, "project-1", "month")?.total_seconds).toBe(180);
    expect(readScreenTimeCache(scope, "project-2", "week")).toBeNull();
  });

  it("does not cache data without a complete tenant/user identity", () => {
    expect(getDashboardCacheScope({ id: 7 })).toBe("");
    writeDashboardMetricsCache("", { forms: 9 });
    expect(readDashboardMetricsCache("")).toBeNull();
  });
});
describe("dashboard request caching", () => {
  it("reuses fresh snapshots without calling the backend", async () => {
    const loader = vi.fn().mockResolvedValue({ forms: 4 });
    await fetchDashboardMetricsCached("owner-a", loader);
    expect(await fetchDashboardMetricsCached("owner-a", loader)).toEqual({ forms: 4 });
    expect(loader).toHaveBeenCalledOnce();
  });

  it("deduplicates concurrent requests for the same account", async () => {
    const loader = vi.fn().mockResolvedValue({ forms: 4 });
    const first = fetchDashboardMetricsCached("owner-a", loader);
    const second = fetchDashboardMetricsCached("owner-a", loader);
    expect(first).toBe(second);
    await first;
    expect(loader).toHaveBeenCalledOnce();
  });

  it("keeps stale data available and refreshes after 30 seconds", async () => {
    const clock = vi.spyOn(Date, "now").mockReturnValue(100_000);
    writeDashboardMetricsCache("owner-a", { forms: 4 });
    clock.mockReturnValue(131_000);
    const loader = vi.fn().mockResolvedValue({ forms: 5 });
    const request = fetchDashboardMetricsCached("owner-a", loader);
    expect(readDashboardMetricsCache("owner-a")).toEqual({ forms: 4 });
    await request;
    expect(readDashboardMetricsCache("owner-a")).toEqual({ forms: 5 });
  });

  it("clears all snapshots on logout and rejects late cache writes", async () => {
    let resolve;
    const pending = fetchDashboardMetricsCached("owner-a", () => new Promise(done => { resolve = done; }));
    await Promise.resolve();
    writeScreenTimeCache("owner-a", "project-1", "week", { total_seconds: 60 });
    clearAllDashboardSnapshotCaches();
    resolve({ forms: 4 });
    await pending;
    expect(readDashboardMetricsCache("owner-a")).toBeNull();
    expect(readScreenTimeCache("owner-a", "project-1", "week")).toBeNull();
    expect(sessionStorage.getItem("madar-dashboard-cache-v1")).toBeNull();
  });

  it("keeps failed refreshes retryable without replacing cached data", async () => {
    writeDashboardMetricsCache("owner-a", { forms: 4 });
    vi.spyOn(Date, "now").mockReturnValue(Date.now() + 31_000);
    await expect(fetchDashboardMetricsCached("owner-a", () => Promise.reject(new Error("Unavailable")))).rejects.toThrow("Unavailable");
    expect(readDashboardMetricsCache("owner-a")).toEqual({ forms: 4 });
    await fetchDashboardMetricsCached("owner-a", () => Promise.resolve({ forms: 5 }));
    expect(readDashboardMetricsCache("owner-a")).toEqual({ forms: 5 });
  });
});
