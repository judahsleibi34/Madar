import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  clearCalendarWorkspaceCache,
  createCalendarWorkspaceCacheKey,
  getOrCreateCalendarWorkspaceRequest,
  readCalendarWorkspaceCache,
  readCalendarWorkspaceCacheEntry,
  writeCalendarWorkspaceCache,
  CALENDAR_WORKSPACE_FRESH_MS,
  CALENDAR_WORKSPACE_STALE_MS,
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

  it("does not reuse an in-flight request after the user cache is invalidated", async () => {
    const key = createCalendarWorkspaceCacheKey({
      userScope: "mutation-user",
      start: "start",
      end: "end",
    });
    let resolveFirst;
    const firstLoader = vi.fn(() => new Promise((resolve) => {
      resolveFirst = resolve;
    }));
    const secondLoader = vi.fn(async () => ({ calendars: [], events: [{ id: "new" }] }));
    const first = getOrCreateCalendarWorkspaceRequest(key, firstLoader);

    clearCalendarWorkspaceCache("mutation-user");
    const second = getOrCreateCalendarWorkspaceRequest(key, secondLoader);

    expect(second).not.toBe(first);
    await expect(second).resolves.toEqual({ calendars: [], events: [{ id: "new" }] });
    resolveFirst({ calendars: [], events: [{ id: "old" }] });
    await first;
    expect(firstLoader).toHaveBeenCalledTimes(1);
    expect(secondLoader).toHaveBeenCalledTimes(1);
  });

  it("serves stale workspace data immediately while identifying it for revalidation", () => {
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000_000);
    const key = createCalendarWorkspaceCacheKey({
      userScope: "stale-user",
      start: "start",
      end: "end",
    });
    const workspace = { calendars: [], events: [{ id: "cached-event" }] };
    writeCalendarWorkspaceCache(key, workspace);

    expect(readCalendarWorkspaceCacheEntry(key)).toMatchObject({
      workspace,
      freshness: "fresh",
    });

    now.mockReturnValue(1_000_000 + CALENDAR_WORKSPACE_FRESH_MS + 1);
    expect(readCalendarWorkspaceCacheEntry(key)).toMatchObject({
      workspace,
      freshness: "stale",
    });
    expect(readCalendarWorkspaceCache(key)).toEqual(workspace);

    now.mockReturnValue(1_000_000 + CALENDAR_WORKSPACE_STALE_MS + 1);
    expect(readCalendarWorkspaceCacheEntry(key)).toBeNull();
    now.mockRestore();
  });
});
