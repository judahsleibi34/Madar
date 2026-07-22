import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearCalendarWorkspaceCache,
  createCalendarWorkspaceCacheKey,
  getOrCreateCalendarWorkspaceRequest,
  readCalendarWorkspaceCache,
  writeCalendarWorkspaceCache,
} from "./calendarWorkspaceCache";

beforeEach(() => window.sessionStorage.clear());

describe("calendar workspace cache", () => {
  it("isolates entries by user and date range and clears one user scope", () => {
    const first = createCalendarWorkspaceCacheKey({ userScope: "user-1", start: "a", end: "b" });
    const second = createCalendarWorkspaceCacheKey({ userScope: "user-2", start: "a", end: "b" });
    const workspace = { calendars: [], events: [{ id: "event-1" }] };
    writeCalendarWorkspaceCache(first, workspace);
    writeCalendarWorkspaceCache(second, workspace);

    expect(readCalendarWorkspaceCache(first)).toEqual(workspace);
    clearCalendarWorkspaceCache("user-1");
    expect(readCalendarWorkspaceCache(first)).toBeNull();
    expect(readCalendarWorkspaceCache(second)).toEqual(workspace);
  });

  it("deduplicates simultaneous workspace requests", async () => {
    const loader = vi.fn(async () => ({ calendars: [], events: [] }));
    const first = getOrCreateCalendarWorkspaceRequest("same", loader);
    const second = getOrCreateCalendarWorkspaceRequest("same", loader);
    expect(first).toBe(second);
    await first;
    expect(loader).toHaveBeenCalledTimes(1);
  });
});
