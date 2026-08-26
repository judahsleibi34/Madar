export const RESPONSES_CACHE_VERSION = 1;

const RESPONSES_CACHE_STORAGE_KEY =
  "madar-builder-responses-cache-v" + RESPONSES_CACHE_VERSION;
const RESPONSES_CACHE_MAX_AGE_MS = 6 * 60 * 60 * 1000;
const RESPONSES_CACHE_MAX_ENTRIES = 30;

const memoryCache = new Map();
const inFlightRequests = new Map();

function readStoredEntries() {
  try {
    const parsed = JSON.parse(
      window.sessionStorage.getItem(RESPONSES_CACHE_STORAGE_KEY) || "{}"
    );
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeStoredEntries(entries) {
  try {
    window.sessionStorage.setItem(
      RESPONSES_CACHE_STORAGE_KEY,
      JSON.stringify(entries)
    );
  } catch {
    // The in-memory cache still works when storage is unavailable or full.
  }
}

function isUsableEntry(entry) {
  return Boolean(
    entry &&
      Array.isArray(entry.responses) &&
      entry.pagination &&
      Number.isFinite(Number(entry.cachedAt)) &&
      Date.now() - Number(entry.cachedAt) <= RESPONSES_CACHE_MAX_AGE_MS
  );
}

export function createResponsesCacheKey({
  userScope,
  projectId,
  formId,
  view = "completed",
  limit,
  offset,
}) {
  return [
    "responses",
    userScope || "authenticated",
    projectId || "project",
    formId || "form",
    view,
    Number(limit) || 0,
    Number(offset) || 0,
  ]
    .map((value) => encodeURIComponent(String(value)))
    .join(":");
}

export function readResponsesCache(cacheKey) {
  if (!cacheKey) return null;

  const memoryEntry = memoryCache.get(cacheKey);
  if (isUsableEntry(memoryEntry)) return memoryEntry;
  if (memoryEntry) memoryCache.delete(cacheKey);

  const entries = readStoredEntries();
  const storedEntry = entries[cacheKey];
  if (!isUsableEntry(storedEntry)) {
    if (storedEntry) {
      delete entries[cacheKey];
      writeStoredEntries(entries);
    }
    return null;
  }

  memoryCache.set(cacheKey, storedEntry);
  return storedEntry;
}

export function writeResponsesCache(cacheKey, responses, pagination) {
  if (!cacheKey || !Array.isArray(responses) || !pagination) return;

  const entry = {
    responses,
    pagination,
    cachedAt: Date.now(),
  };
  memoryCache.set(cacheKey, entry);

  const entries = readStoredEntries();
  entries[cacheKey] = entry;

  const orderedKeys = Object.keys(entries).sort(
    (first, second) =>
      Number(entries[second]?.cachedAt || 0) -
      Number(entries[first]?.cachedAt || 0)
  );
  orderedKeys.slice(RESPONSES_CACHE_MAX_ENTRIES).forEach((key) => {
    delete entries[key];
    memoryCache.delete(key);
  });

  writeStoredEntries(entries);
}

export function getOrCreateResponsesRequest(cacheKey, loader) {
  const activeRequest = inFlightRequests.get(cacheKey);
  if (activeRequest) return activeRequest;

  const request = Promise.resolve()
    .then(loader)
    .finally(() => {
      if (inFlightRequests.get(cacheKey) === request) {
        inFlightRequests.delete(cacheKey);
      }
    });
  inFlightRequests.set(cacheKey, request);
  return request;
}
