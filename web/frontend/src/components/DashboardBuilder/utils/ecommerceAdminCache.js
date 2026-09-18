const DEFAULT_FRESH_MS = 30_000;
const MAX_ENTRIES = 80;
const STORAGE_KEY = "madar-ecommerce-admin-cache-v1";
const RETAIN_MS = 24 * 60 * 60 * 1000;
const entries = new Map();
const requests = new Map();

const keyFor = (scope, resource) =>
  `${encodeURIComponent(String(scope || "authenticated"))}::${String(resource)}`;

export function getEcommerceCacheScope(user) {
  if (!user?.id && !user?.auth_id) return "authenticated";
  return `tenant:${encodeURIComponent(String(user?.tenant_id ?? "unknown"))}:user:${encodeURIComponent(String(user.id ?? user.auth_id))}`;
}

function storedEntries() {
  try { return JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || "{}"); } catch { return {}; }
}

function persistEntries() {
  try { window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(Object.fromEntries(entries))); } catch { /* Memory cache still works. */ }
}

export function readEcommerceAdminCacheSnapshot(scope, resource) {
  const key = keyFor(scope, resource);
  const entry = entries.get(key) || storedEntries()?.[key];
  const age = Date.now() - Number(entry?.cachedAt);
  if (!entry || !Number.isFinite(age) || age < 0 || age > RETAIN_MS) return null;
  entries.delete(key);
  entries.set(key, entry);
  while (entries.size > MAX_ENTRIES) entries.delete(entries.keys().next().value);
  return { data: entry.data, cachedAt: entry.cachedAt, isStale: age >= DEFAULT_FRESH_MS };
}

export function readEcommerceAdminCache(scope, resource, freshMs = DEFAULT_FRESH_MS) {
  const snapshot = readEcommerceAdminCacheSnapshot(scope, resource);
  return snapshot && Date.now() - snapshot.cachedAt < freshMs ? snapshot.data : null;
}

export function writeEcommerceAdminCache(scope, resource, data) {
  Object.entries(storedEntries() || {}).forEach(([key, entry]) => { if (!entries.has(key) && Number.isFinite(Number(entry?.cachedAt)) && Date.now() - entry.cachedAt <= RETAIN_MS) entries.set(key, entry); });
  const key = keyFor(scope, resource);
  entries.delete(key);
  entries.set(key, { cachedAt: Date.now(), data });
  while (entries.size > MAX_ENTRIES) entries.delete(entries.keys().next().value);
  persistEntries();
  return data;
}

export function loadEcommerceAdminResource(scope, resource, loader, { force = false, freshMs } = {}) {
  const key = keyFor(scope, resource);
  if (!force) {
    const cached = readEcommerceAdminCache(scope, resource, freshMs);
    if (cached !== null) return Promise.resolve(cached);
  }
  const pending = requests.get(key);
  if (pending) return pending;
  const request = Promise.resolve()
    .then(loader)
    .then((data) => {
      // A mutation or logout can invalidate this request while it is in flight.
      if (requests.get(key) === request) writeEcommerceAdminCache(scope, resource, data);
      return data;
    })
    .finally(() => {
      if (requests.get(key) === request) requests.delete(key);
    });
  requests.set(key, request);
  return request;
}

export function clearEcommerceAdminCache(scope, resourcePrefix = "") {
  const scopePrefix = scope == null ? null : `${encodeURIComponent(String(scope || "authenticated"))}::`;
  const stored = storedEntries();
  Object.entries(stored || {}).forEach(([key, entry]) => { if (!entries.has(key)) entries.set(key, entry); });
  [...entries.keys(), ...requests.keys()].forEach((key) => {
    const belongsToScope = scopePrefix == null || key.startsWith(scopePrefix);
    const resource = key.slice(key.indexOf("::") + 2);
    if (belongsToScope && resource.startsWith(resourcePrefix)) {
      entries.delete(key);
      requests.delete(key);
    }
  });
  persistEntries();
}
