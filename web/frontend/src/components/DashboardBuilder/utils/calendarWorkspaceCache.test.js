import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  CALENDAR_WORKSPACE_CACHE_STORAGE_KEY,
  CALENDAR_WORKSPACE_CACHE_VERSION,
  CALENDAR_WORKSPACE_FRESH_MS,
  CALENDAR_WORKSPACE_STALE_MS,
  clearAllCalendarWorkspaceCaches,
  clearCalendarWorkspaceCache,
  createCalendarWorkspaceCacheKey,
  getOrCreateCalendarWorkspaceRequest,
  readCalendarWorkspaceCache,
  readCalendarWorkspaceCacheEntry,
  writeCalendarWorkspaceCache,
} from "./calendarWorkspaceCache";

const tenantA = { tenantScope: "tenant-a", userScope: "user-1" };
const tenantB = { tenantScope: "tenant-b", userScope: "user-1" };
const range = { start: "2026-08-01", end: "2026-08-08" };

const keyFor = (identity, requestedRange = range) =>
  createCalendarWorkspaceCacheKey({ ...identity, ...requestedRange });

beforeEach(() => {
  clearAllCalendarWorkspaceCaches();
  window.sessionStorage.clear();
});

describe("calendar workspace cache", () => {
  it("includes cache version, tenant, user, and range in cache identity", () => {
    const first = keyFor(tenantA);
    const otherTenant = keyFor(tenantB);
    const otherUser = keyFor({ ...tenantA, userScope: "user-2" });
    const otherRange = keyFor(tenantA, { start: range.start, end: "2026-08-09" });

    expect(first).toContain(`v${CALENDAR_WORKSPACE_CACHE_VERSION}`);
    expect(new Set([first, otherTenant, otherUser, otherRange]).size).toBe(4);
  });

  it("never returns one tenant's workspace for the same user and range in another tenant", () => {
    const tenantAWorkspace = { calendars: [], events: [{ id: "tenant-a-event" }] };
    writeCalendarWorkspaceCache(keyFor(tenantA), tenantAWorkspace, tenantA);

    expect(readCalendarWorkspaceCache(keyFor(tenantB), tenantB)).toBeNull();
    expect(readCalendarWorkspaceCache(keyFor(tenantA), tenantB)).toBeNull();
    expect(readCalendarWorkspaceCache(keyFor(tenantA), tenantA)).toEqual(tenantAWorkspace);
  });

  it("returns a valid hit only for the same tenant, user, and range", () => {
    const workspace = { calendars: [], events: [{ id: "matching-event" }] };
    const key = keyFor(tenantA);
    writeCalendarWorkspaceCache(key, workspace, tenantA);

    expect(readCalendarWorkspaceCache(key, tenantA)).toEqual(workspace);
    expect(readCalendarWorkspaceCacheEntry(key, tenantA)).toMatchObject({
      workspace,
      freshness: "fresh",
    });
  });

  it("rejects tenantless entries and removes the legacy cache schema", () => {
    const key = keyFor(tenantA);
    const tenantlessEntry = {
      cacheVersion: CALENDAR_WORKSPACE_CACHE_VERSION,
      workspace: { calendars: [], events: [{ id: "legacy-event" }] },
      cachedAt: Date.now(),
    };
    window.sessionStorage.setItem(
      CALENDAR_WORKSPACE_CACHE_STORAGE_KEY,
      JSON.stringify({ [key]: tenantlessEntry })
    );
    window.sessionStorage.setItem(
      "madar-calendar-workspace-cache-v1",
      JSON.stringify({ legacy: tenantlessEntry })
    );

    expect(readCalendarWorkspaceCache(key, tenantA)).toBeNull();
    expect(window.sessionStorage.getItem("madar-calendar-workspace-cache-v1")).toBeNull();
    expect(JSON.parse(
      window.sessionStorage.getItem(CALENDAR_WORKSPACE_CACHE_STORAGE_KEY) || "{}"
    )).toEqual({});
  });

  it("fails closed instead of caching when tenant or user identity is missing", async () => {
    const loader = vi.fn(async () => ({ calendars: [], events: [] }));
    const key = createCalendarWorkspaceCacheKey({
      tenantScope: "",
      userScope: "user-1",
      ...range,
    });

    expect(key).toBe("");
    const first = getOrCreateCalendarWorkspaceRequest(key, loader);
    const second = getOrCreateCalendarWorkspaceRequest(key, loader);
    expect(first).not.toBe(second);
    await Promise.all([first, second]);
    expect(loader).toHaveBeenCalledTimes(2);
  });

  it("clears only the requested tenant and user namespace", () => {
    const first = keyFor(tenantA);
    const second = keyFor(tenantB);
    const workspace = { calendars: [], events: [{ id: "event-1" }] };
    writeCalendarWorkspaceCache(first, workspace, tenantA);
    writeCalendarWorkspaceCache(second, workspace, tenantB);

    clearCalendarWorkspaceCache(tenantA);
    expect(readCalendarWorkspaceCache(first, tenantA)).toBeNull();
    expect(readCalendarWorkspaceCache(second, tenantB)).toEqual(workspace);
  });

  it("clears every current-tab tenant cache during session cleanup", () => {
    const workspace = { calendars: [], events: [{ id: "session-event" }] };
    writeCalendarWorkspaceCache(keyFor(tenantA), workspace, tenantA);
    writeCalendarWorkspaceCache(keyFor(tenantB), workspace, tenantB);

    clearAllCalendarWorkspaceCaches();

    expect(readCalendarWorkspaceCache(keyFor(tenantA), tenantA)).toBeNull();
    expect(readCalendarWorkspaceCache(keyFor(tenantB), tenantB)).toBeNull();
    expect(
      window.sessionStorage.getItem(CALENDAR_WORKSPACE_CACHE_STORAGE_KEY)
    ).toBeNull();
  });

  it("deduplicates simultaneous workspace requests within one identity key", async () => {
    const loader = vi.fn(async () => ({ calendars: [], events: [] }));
    const key = keyFor(tenantA);
    const first = getOrCreateCalendarWorkspaceRequest(key, loader);
    const second = getOrCreateCalendarWorkspaceRequest(key, loader);
    expect(first).toBe(second);
    await first;
    expect(loader).toHaveBeenCalledTimes(1);
  });

  it("does not reuse an in-flight request after its tenant namespace is invalidated", async () => {
    const key = keyFor(tenantA);
    let resolveFirst;
    const firstLoader = vi.fn(() => new Promise((resolve) => {
      resolveFirst = resolve;
    }));
    const secondLoader = vi.fn(async () => ({ calendars: [], events: [{ id: "new" }] }));
    const first = getOrCreateCalendarWorkspaceRequest(key, firstLoader);

    clearCalendarWorkspaceCache(tenantA);
    const second = getOrCreateCalendarWorkspaceRequest(key, secondLoader);

    expect(second).not.toBe(first);
    await expect(second).resolves.toEqual({ calendars: [], events: [{ id: "new" }] });
    resolveFirst({ calendars: [], events: [{ id: "old" }] });
    await first;
    expect(firstLoader).toHaveBeenCalledTimes(1);
    expect(secondLoader).toHaveBeenCalledTimes(1);
  });

  it("serves matching stale data for revalidation but expires it at the stale limit", () => {
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000_000);
    const key = keyFor(tenantA);
    const workspace = { calendars: [], events: [{ id: "cached-event" }] };
    writeCalendarWorkspaceCache(key, workspace, tenantA);

    expect(readCalendarWorkspaceCacheEntry(key, tenantA)).toMatchObject({
      workspace,
      freshness: "fresh",
    });

    now.mockReturnValue(1_000_000 + CALENDAR_WORKSPACE_FRESH_MS + 1);
    expect(readCalendarWorkspaceCacheEntry(key, tenantA)).toMatchObject({
      workspace,
      freshness: "stale",
    });

    now.mockReturnValue(1_000_000 + CALENDAR_WORKSPACE_STALE_MS + 1);
    expect(readCalendarWorkspaceCacheEntry(key, tenantA)).toBeNull();
    now.mockRestore();
  });
});
