export const ECOMMERCE_CATALOG_CACHE_VERSION = 2;

const STORAGE_KEY = `madar-ecommerce-catalog-cache-v${ECOMMERCE_CATALOG_CACHE_VERSION}`;
const MAX_AGE_MS = 3 * 60 * 1000;
const STALE_MAX_AGE_MS = 24 * 60 * 60 * 1000;
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

function isTheme(value) {
  return Boolean(
    value &&
      ["accent", "background", "surface", "text", "muted"].every(
        (key) => typeof value[key] === "string",
      ),
  );
}

function cacheAge(entry) {
  return Date.now() - Number(entry?.cachedAt);
}

function isRetained(entry) {
  return Boolean(
    isCatalog(entry?.catalog) &&
      Number.isFinite(Number(entry.cachedAt)) &&
      cacheAge(entry) <= STALE_MAX_AGE_MS,
  );
}

export function readEcommerceCatalogCacheSnapshot(scope) {
  const key = cacheKey(scope);
  let entry = memoryCache.get(key);

  if (!isRetained(entry)) {
    if (entry) memoryCache.delete(key);
    const entries = readStoredEntries();
    entry = entries[key];
    if (!isRetained(entry)) {
      if (entry) {
        delete entries[key];
        writeStoredEntries(entries);
      }
      return null;
    }
    memoryCache.set(key, entry);
  }

  return {
    catalog: entry.catalog,
    cachedAt: Number(entry.cachedAt),
    isStale: cacheAge(entry) > MAX_AGE_MS,
  };
}

export function readEcommerceCatalogCache(scope) {
  const snapshot = readEcommerceCatalogCacheSnapshot(scope);
  return snapshot && !snapshot.isStale ? snapshot.catalog : null;
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


export function updateEcommerceCatalogCache(scope, section, item) {
  const snapshot = readEcommerceCatalogCacheSnapshot(scope);
  if (!snapshot || !Array.isArray(snapshot.catalog?.[section]) || !item?.id) return;
  const currentItems = snapshot.catalog[section];
  const nextItems = currentItems.some((candidate) => candidate.id === item.id)
    ? currentItems.map((candidate) => candidate.id === item.id ? item : candidate)
    : [item, ...currentItems];
  writeEcommerceCatalogCache(scope, { ...snapshot.catalog, [section]: nextItems });
}

export function removeFromEcommerceCatalogCache(scope, section, itemId) {
  const snapshot = readEcommerceCatalogCacheSnapshot(scope);
  if (!snapshot || !Array.isArray(snapshot.catalog?.[section])) return;
  writeEcommerceCatalogCache(scope, {
    ...snapshot.catalog,
    [section]: snapshot.catalog[section].filter((candidate) => candidate.id !== itemId),
  });
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
export function readEcommerceThemeCacheSnapshot(scope) {
  const key = `theme:${encodeURIComponent(String(scope || "authenticated"))}`;
  let entry = memoryCache.get(key);
  if (!entry) {
    entry = readStoredEntries()[key];
    if (entry) memoryCache.set(key, entry);
  }
  if (!isTheme(entry?.theme) || !Number.isFinite(Number(entry.cachedAt)) || cacheAge(entry) > STALE_MAX_AGE_MS) return null;
  return { theme: entry.theme, cachedAt: Number(entry.cachedAt), isStale: cacheAge(entry) > MAX_AGE_MS };
}

export function readEcommerceThemeCache(scope) {
  const snapshot = readEcommerceThemeCacheSnapshot(scope);
  return snapshot && !snapshot.isStale ? snapshot.theme : null;
}

export function writeEcommerceThemeCache(scope, theme) {
  if (!isTheme(theme)) return;
  const key = `theme:${encodeURIComponent(String(scope || "authenticated"))}`;
  const entry = { theme, cachedAt: Date.now() };
  memoryCache.set(key, entry);
  const entries = readStoredEntries();
  entries[key] = entry;
  writeStoredEntries(entries);
}

export function clearEcommerceThemeCache(scope) {
  const key = `theme:${encodeURIComponent(String(scope || "authenticated"))}`;
  memoryCache.delete(key);
  inFlightRequests.delete(key);
  const entries = readStoredEntries();
  if (entries[key]) {
    delete entries[key];
    writeStoredEntries(entries);
  }
}

export function getOrCreateEcommerceThemeRequest(scope, loader) {
  const key = `theme:${encodeURIComponent(String(scope || "authenticated"))}`;
  const activeRequest = inFlightRequests.get(key);
  if (activeRequest) return activeRequest;
  const request = Promise.resolve().then(loader).finally(() => {
    if (inFlightRequests.get(key) === request) inFlightRequests.delete(key);
  });
  inFlightRequests.set(key, request);
  return request;
}
