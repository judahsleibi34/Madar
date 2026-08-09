export const CALENDAR_WORKSPACE_CACHE_VERSION = 1;

const STORAGE_KEY = `madar-calendar-workspace-cache-v${CALENDAR_WORKSPACE_CACHE_VERSION}`;
export const CALENDAR_WORKSPACE_FRESH_MS = 5 * 60 * 1000;
export const CALENDAR_WORKSPACE_STALE_MS = 30 * 60 * 1000;
const MAX_ENTRIES = 24;
const memoryCache = new Map();
const inFlightRequests = new Map();

function readStoredEntries() {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || "{}");
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

function writeStoredEntries(entries) {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // The memory cache remains available when session storage is unavailable.
  }
}

function isStructurallyValid(entry) {
  return Boolean(
    entry?.workspace &&
      Array.isArray(entry.workspace.calendars) &&
      Array.isArray(entry.workspace.events) &&
      Number.isFinite(Number(entry.cachedAt))
  );
}

function classifyEntry(entry) {
  if (!isStructurallyValid(entry)) return null;
  const ageMs = Math.max(0, Date.now() - Number(entry.cachedAt));
  if (ageMs > CALENDAR_WORKSPACE_STALE_MS) return null;
  return {
    workspace: entry.workspace,
    cachedAt: Number(entry.cachedAt),
    ageMs,
    freshness: ageMs <= CALENDAR_WORKSPACE_FRESH_MS ? "fresh" : "stale",
  };
}

export function createCalendarWorkspaceCacheKey({ userScope, start, end }) {
  return ["calendar", userScope || "authenticated", start, end]
    .map((value) => encodeURIComponent(String(value || "")))
    .join(":");
}

export function readCalendarWorkspaceCache(cacheKey) {
  return readCalendarWorkspaceCacheEntry(cacheKey)?.workspace || null;
}

export function readCalendarWorkspaceCacheEntry(cacheKey) {
  if (!cacheKey) return null;
  const memoryEntry = memoryCache.get(cacheKey);
  const memoryResult = classifyEntry(memoryEntry);
  if (memoryResult) return memoryResult;
  if (memoryEntry) memoryCache.delete(cacheKey);

  const entries = readStoredEntries();
  const storedEntry = entries[cacheKey];
  const storedResult = classifyEntry(storedEntry);
  if (!storedResult) {
    if (storedEntry) {
      delete entries[cacheKey];
      writeStoredEntries(entries);
    }
    return null;
  }
  memoryCache.set(cacheKey, storedEntry);
  return storedResult;
}

export function writeCalendarWorkspaceCache(cacheKey, workspace) {
  if (!cacheKey || !workspace || !Array.isArray(workspace.events)) return;
  const entry = { workspace, cachedAt: Date.now() };
  memoryCache.set(cacheKey, entry);

  const entries = readStoredEntries();
  entries[cacheKey] = entry;
  Object.keys(entries)
    .sort((first, second) => Number(entries[second]?.cachedAt || 0) - Number(entries[first]?.cachedAt || 0))
    .slice(MAX_ENTRIES)
    .forEach((key) => {
      delete entries[key];
      memoryCache.delete(key);
    });
  writeStoredEntries(entries);
}

export function clearCalendarWorkspaceCache(userScope) {
  const prefix = ["calendar", userScope || "authenticated"]
    .map((value) => encodeURIComponent(String(value)))
    .join(":") + ":";
  const entries = readStoredEntries();
  Object.keys(entries).forEach((key) => {
    if (key.startsWith(prefix)) delete entries[key];
  });
  Array.from(memoryCache.keys()).forEach((key) => {
    if (key.startsWith(prefix)) memoryCache.delete(key);
  });
  Array.from(inFlightRequests.keys()).forEach((key) => {
    if (key.startsWith(prefix)) inFlightRequests.delete(key);
  });
  writeStoredEntries(entries);
}

export function getOrCreateCalendarWorkspaceRequest(cacheKey, loader) {
  const activeRequest = inFlightRequests.get(cacheKey);
  if (activeRequest) return activeRequest;
  const request = Promise.resolve()
    .then(loader)
    .finally(() => {
      if (inFlightRequests.get(cacheKey) === request) inFlightRequests.delete(cacheKey);
    });
  inFlightRequests.set(cacheKey, request);
  return request;
}
