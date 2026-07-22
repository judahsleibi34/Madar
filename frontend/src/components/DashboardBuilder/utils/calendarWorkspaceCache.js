export const CALENDAR_WORKSPACE_CACHE_VERSION = 1;

const STORAGE_KEY = `madar-calendar-workspace-cache-v${CALENDAR_WORKSPACE_CACHE_VERSION}`;
const MAX_AGE_MS = 5 * 60 * 1000;
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

function isUsable(entry) {
  return Boolean(
    entry?.workspace &&
      Array.isArray(entry.workspace.calendars) &&
      Array.isArray(entry.workspace.events) &&
      Number.isFinite(Number(entry.cachedAt)) &&
      Date.now() - Number(entry.cachedAt) <= MAX_AGE_MS
  );
}

export function createCalendarWorkspaceCacheKey({ userScope, start, end }) {
  return ["calendar", userScope || "authenticated", start, end]
    .map((value) => encodeURIComponent(String(value || "")))
    .join(":");
}

export function readCalendarWorkspaceCache(cacheKey) {
  if (!cacheKey) return null;
  const memoryEntry = memoryCache.get(cacheKey);
  if (isUsable(memoryEntry)) return memoryEntry.workspace;
  if (memoryEntry) memoryCache.delete(cacheKey);

  const entries = readStoredEntries();
  const storedEntry = entries[cacheKey];
  if (!isUsable(storedEntry)) {
    if (storedEntry) {
      delete entries[cacheKey];
      writeStoredEntries(entries);
    }
    return null;
  }
  memoryCache.set(cacheKey, storedEntry);
  return storedEntry.workspace;
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
