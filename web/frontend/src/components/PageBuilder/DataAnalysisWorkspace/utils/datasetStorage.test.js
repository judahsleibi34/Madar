import { describe, expect, it } from "vitest";

import {
  archiveItem,
  getProjectArchiveScope,
  getTenantUserArchiveScope,
  listArchiveItems,
} from "./datasetStorage";


describe("calendar/local archive scoping", () => {
  it("namespaces the same user independently in each authoritative tenant", () => {
    expect(getTenantUserArchiveScope({ id: "user-7", tenant_id: "tenant-a" })).toBe(
      "archive:v2:tenant:tenant-a:user:user-7"
    );
    expect(getTenantUserArchiveScope({ id: "user-7", tenant_id: "tenant-b" })).toBe(
      "archive:v2:tenant:tenant-b:user:user-7"
    );
  });

  it("fails closed when either tenant or user identity is missing", async () => {
    expect(getTenantUserArchiveScope({ id: "user-7" })).toBe("");
    expect(getTenantUserArchiveScope({ tenant_id: "tenant-a" })).toBe("");
    await expect(listArchiveItems()).resolves.toEqual([]);
  });

  it("does not reuse the legacy user-only namespace", () => {
    const scoped = getTenantUserArchiveScope({ id: "user-7", tenant_id: "tenant-a" });
    expect(scoped).not.toBe("user-user-7");
    expect(scoped.startsWith("archive:v2:")).toBe(true);
  });

  it("keeps data-workspace artifacts under the selected project root", () => {
    expect(getProjectArchiveScope(
      { id: "user-7", tenant_id: "tenant-a" },
      "project/quarterly"
    )).toBe("archive:v2:tenant:tenant-a:user:user-7:project:project%2Fquarterly");
    expect(getProjectArchiveScope({ id: "user-7", tenant_id: "tenant-a" }, "")).toBe("");
  });

  it("rejects archive writes without authoritative tenant and user scope", async () => {
    await expect(archiveItem({ id: "task-1", scope: "user-user-7" })).rejects.toThrow(
      "tenant- and user-scoped"
    );
  });
});
