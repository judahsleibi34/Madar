import { beforeEach, describe, expect, it } from "vitest";
import {
  getDashboardCacheScope,
  readDashboardMetricsCache,
  readScreenTimeCache,
  writeDashboardMetricsCache,
  writeScreenTimeCache,
} from "./dashboardSnapshotCache";

describe("dashboard snapshot cache", () => {
  beforeEach(() => window.sessionStorage.clear());

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