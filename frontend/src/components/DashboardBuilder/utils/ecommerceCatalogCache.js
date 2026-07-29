export const ECOMMERCE_CATALOG_CACHE_VERSION = 1;

const STORAGE_KEY = `madar-ecommerce-catalog-cache-v${ECOMMERCE_CATALOG_CACHE_VERSION}`;
const MAX_AGE_MS = 3 * 60 * 1000;
const MAX_ENTRIES = 8;
const memoryCache = new Map();
const inFlightRequests = new Map();

function cacheKey(scope) {
  return `catalog:${encodeURIComponent(String(scope || "authenticated"))}`;
}

function readStoredEntries() {
  try {
    const value = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || "{}");
    return value && typeof value === "object" && !Array.isArray(value) ? value : {};
  } catch {
    return {};
  }
}

function writeStoredEntries(entries) {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Memory caching remains available when session storage is unavailable.
  }
}

function isCatalog(value) {
  return Boolean(
    value &&
      Array.isArray(value.tags) &&
      Array.isArray(value.categories) &&
      Array.isArray(value.products),
  );
}

function isUsable(entry) {
  return Boolean(
    isCatalog(entry?.catalog) &&
      Number.isFinite(Number(entry.cachedAt)) &&
      Date.now() - Number(entry.cachedAt) <= MAX_AGE_MS,
  );
}

export function readEcommerceCatalogCache(scope) {
  const key = cacheKey(scope);
  const memoryEntry = memoryCache.get(key);
  if (isUsable(memoryEntry)) return memoryEntry.catalog;
  if (memoryEntry) memoryCache.delete(key);

  const entries = readStoredEntries();
  const storedEntry = entries[key];
  if (!isUsable(storedEntry)) {
    if (storedEntry) {
      delete entries[key];
      writeStoredEntries(entries);
    }
    return null;
  }
  memoryCache.set(key, storedEntry);
  return storedEntry.catalog;
}

export function writeEcommerceCatalogCache(scope, catalog) {
  if (!isCatalog(catalog)) return;
  const key = cacheKey(scope);
  const entry = { catalog, cachedAt: Date.now() };
  memoryCache.set(key, entry);

  const entries = readStoredEntries();
  entries[key] = entry;
  Object.keys(entries)
    .sort((first, second) => Number(entries[second]?.cachedAt || 0) - Number(entries[first]?.cachedAt || 0))
    .slice(MAX_ENTRIES)
    .forEach((oldKey) => {
      delete entries[oldKey];
      memoryCache.delete(oldKey);
    });
  writeStoredEntries(entries);
}

export function clearEcommerceCatalogCache(scope) {
  const key = cacheKey(scope);
  memoryCache.delete(key);
  inFlightRequests.delete(key);
  const entries = readStoredEntries();
  if (entries[key]) {
    delete entries[key];
    writeStoredEntries(entries);
  }
}

export function getOrCreateEcommerceCatalogRequest(scope, loader) {
  const key = cacheKey(scope);
  const activeRequest = inFlightRequests.get(key);
  if (activeRequest) return activeRequest;
  const request = Promise.resolve()
    .then(loader)
    .finally(() => {
      if (inFlightRequests.get(key) === request) inFlightRequests.delete(key);
    });
  inFlightRequests.set(key, request);
  return request;
}
