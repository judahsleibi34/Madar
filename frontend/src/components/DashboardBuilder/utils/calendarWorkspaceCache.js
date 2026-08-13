export const CALENDAR_WORKSPACE_CACHE_VERSION = 2;

export const CALENDAR_WORKSPACE_CACHE_STORAGE_KEY =
  `madar-calendar-workspace-cache-v${CALENDAR_WORKSPACE_CACHE_VERSION}`;
const LEGACY_STORAGE_KEYS = ["madar-calendar-workspace-cache-v1"];
export const CALENDAR_WORKSPACE_FRESH_MS = 5 * 60 * 1000;
export const CALENDAR_WORKSPACE_STALE_MS = 30 * 60 * 1000;
const MAX_ENTRIES = 24;
const memoryCache = new Map();
const inFlightRequests = new Map();

function readStoredEntries() {
  try {
    LEGACY_STORAGE_KEYS.forEach((key) => window.sessionStorage.removeItem(key));
    const value = JSON.parse(
      window.sessionStorage.getItem(CALENDAR_WORKSPACE_CACHE_STORAGE_KEY) || "{}"
    );
    return value && typeof value === "object" ? value : {};
  } catch {
    return {};
  }
}

function writeStoredEntries(entries) {
  try {
    window.sessionStorage.setItem(
      CALENDAR_WORKSPACE_CACHE_STORAGE_KEY,
      JSON.stringify(entries)
    );
  } catch {
    // The memory cache remains available when session storage is unavailable.
  }
}

function normalizeScope(value) {
  return String(value ?? "").trim();
}

function normalizeIdentity(identity) {
  const tenantScope = normalizeScope(identity?.tenantScope);
  const userScope = normalizeScope(identity?.userScope);
  return tenantScope && userScope ? { tenantScope, userScope } : null;
}

function cacheIdentityPrefix(identity) {
  const normalized = normalizeIdentity(identity);
  if (!normalized) return "";
  return [
    "calendar",
    `v${CALENDAR_WORKSPACE_CACHE_VERSION}`,
    normalized.tenantScope,
    normalized.userScope,
  ]
    .map((value) => encodeURIComponent(value))
    .join(":") + ":";
}

function isStructurallyValid(entry, identity) {
  const normalized = normalizeIdentity(identity);
  return Boolean(
    normalized &&
      entry?.cacheVersion === CALENDAR_WORKSPACE_CACHE_VERSION &&
      entry?.tenantScope === normalized.tenantScope &&
      entry?.userScope === normalized.userScope &&
      entry?.workspace &&
      Array.isArray(entry.workspace.calendars) &&
      Array.isArray(entry.workspace.events) &&
      Number.isFinite(Number(entry.cachedAt))
  );
}

function classifyEntry(entry, identity) {
  if (!isStructurallyValid(entry, identity)) return null;
  const ageMs = Math.max(0, Date.now() - Number(entry.cachedAt));
  if (ageMs > CALENDAR_WORKSPACE_STALE_MS) return null;
  return {
    workspace: entry.workspace,
    cachedAt: Number(entry.cachedAt),
    ageMs,
    freshness: ageMs <= CALENDAR_WORKSPACE_FRESH_MS ? "fresh" : "stale",
  };
}

export function createCalendarWorkspaceCacheKey({ tenantScope, userScope, start, end }) {
  const identity = normalizeIdentity({ tenantScope, userScope });
  if (!identity) return "";
  return [
    "calendar",
    `v${CALENDAR_WORKSPACE_CACHE_VERSION}`,
    identity.tenantScope,
    identity.userScope,
    start,
    end,
  ]
    .map((value) => encodeURIComponent(String(value || "")))
    .join(":");
}

export function readCalendarWorkspaceCache(cacheKey, identity) {
  return readCalendarWorkspaceCacheEntry(cacheKey, identity)?.workspace || null;
}

export function readCalendarWorkspaceCacheEntry(cacheKey, identity) {
  const prefix = cacheIdentityPrefix(identity);
  if (!cacheKey || !prefix || !cacheKey.startsWith(prefix)) return null;
  const memoryEntry = memoryCache.get(cacheKey);
  const memoryResult = classifyEntry(memoryEntry, identity);
  if (memoryResult) return memoryResult;
  if (memoryEntry) memoryCache.delete(cacheKey);

  const entries = readStoredEntries();
  const storedEntry = entries[cacheKey];
  const storedResult = classifyEntry(storedEntry, identity);
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

export function writeCalendarWorkspaceCache(cacheKey, workspace, identity) {
  const normalized = normalizeIdentity(identity);
  const prefix = cacheIdentityPrefix(normalized);
  if (
    !cacheKey ||
    !prefix ||
    !cacheKey.startsWith(prefix) ||
    !workspace ||
    !Array.isArray(workspace.events)
  ) return;
  const entry = {
    cacheVersion: CALENDAR_WORKSPACE_CACHE_VERSION,
    tenantScope: normalized.tenantScope,
    userScope: normalized.userScope,
    workspace,
    cachedAt: Date.now(),
  };
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

export function clearCalendarWorkspaceCache(identity) {
  const prefix = cacheIdentityPrefix(identity);
  if (!prefix) return;
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

export function clearAllCalendarWorkspaceCaches() {
  memoryCache.clear();
  inFlightRequests.clear();
  try {
    window.sessionStorage.removeItem(CALENDAR_WORKSPACE_CACHE_STORAGE_KEY);
    LEGACY_STORAGE_KEYS.forEach((key) => window.sessionStorage.removeItem(key));
  } catch {
    // In-memory state is still cleared when session storage is unavailable.
  }
}

export function getOrCreateCalendarWorkspaceRequest(cacheKey, loader) {
  if (!cacheKey) return Promise.resolve().then(loader);
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
