import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ArchivePage from "./ArchivePage";
import { fetchArchivedCalendarTasks } from "../PageBuilder/services/PageBuilder.api";
import { listArchiveItems } from "../PageBuilder/DataAnalysisWorkspace/utils/datasetStorage";


vi.mock("../PageBuilder/services/PageBuilder.api", () => ({
  fetchArchivedCalendarTasks: vi.fn(),
}));

vi.mock("../PageBuilder/DataAnalysisWorkspace/utils/datasetStorage", () => ({
  deleteArchiveItem: vi.fn(),
  getTenantUserArchiveScope: (user) => (
    user?.tenant_id && user?.id
      ? `archive:v2:tenant:${user.tenant_id}:user:${user.id}`
      : ""
  ),
  listArchiveItems: vi.fn(),
}));

const archivedItem = (id, title) => ({
  id,
  type: "task",
  title,
  createdAt: "2026-08-10T12:00:00Z",
  payload: { task: { status: "done" } },
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("ArchivePage tenant transitions", () => {
  it("clears Tenant A immediately and loads only Tenant B's namespace", async () => {
    let resolveTenantB;
    listArchiveItems.mockImplementation(({ scope }) => {
      if (scope.includes("tenant-a")) return Promise.resolve([archivedItem("a", "Tenant A task")]);
      return new Promise((resolve) => { resolveTenantB = resolve; });
    });
    fetchArchivedCalendarTasks.mockResolvedValue([]);

    const { rerender } = render(<ArchivePage user={{ id: "user-1", tenant_id: "tenant-a" }} />);
    expect(await screen.findByText("Tenant A task")).toBeTruthy();

    rerender(<ArchivePage user={{ id: "user-1", tenant_id: "tenant-b" }} />);
    expect(screen.queryByText("Tenant A task")).toBeNull();

    await waitFor(() => expect(resolveTenantB).toEqual(expect.any(Function)));
    resolveTenantB([archivedItem("b", "Tenant B task")]);
    expect(await screen.findByText("Tenant B task")).toBeTruthy();
    expect(listArchiveItems).toHaveBeenCalledWith({
      scope: "archive:v2:tenant:tenant-b:user:user-1",
    });
  });

  it("ignores a late Tenant A read after Tenant B becomes authoritative", async () => {
    let resolveTenantA;
    listArchiveItems.mockImplementation(({ scope }) => (
      scope.includes("tenant-a")
        ? new Promise((resolve) => { resolveTenantA = resolve; })
        : Promise.resolve([archivedItem("b", "Tenant B task")])
    ));
    fetchArchivedCalendarTasks.mockResolvedValue([]);

    const { rerender } = render(<ArchivePage user={{ id: "user-1", tenant_id: "tenant-a" }} />);
    await waitFor(() => expect(listArchiveItems).toHaveBeenCalledTimes(1));
    rerender(<ArchivePage user={{ id: "user-1", tenant_id: "tenant-b" }} />);
    expect(await screen.findByText("Tenant B task")).toBeTruthy();

    resolveTenantA([archivedItem("a", "Late Tenant A task")]);
    await Promise.resolve();
    expect(screen.queryByText("Late Tenant A task")).toBeNull();
    expect(screen.getByText("Tenant B task")).toBeTruthy();
  });
});
