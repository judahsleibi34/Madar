const DEFAULT_FRESH_MS = 45_000;
const MAX_ENTRIES = 80;
const entries = new Map();
const requests = new Map();

const keyFor = (scope, resource) =>
  `${encodeURIComponent(String(scope || "authenticated"))}::${String(resource)}`;

export function readEcommerceAdminCache(scope, resource, freshMs = DEFAULT_FRESH_MS) {
  const key = keyFor(scope, resource);
  const entry = entries.get(key);
  if (!entry || Date.now() - entry.cachedAt > freshMs) {
    if (entry) entries.delete(key);
    return null;
  }
  entries.delete(key);
  entries.set(key, entry);
  return entry.data;
}

export function writeEcommerceAdminCache(scope, resource, data) {
  const key = keyFor(scope, resource);
  entries.delete(key);
  entries.set(key, { cachedAt: Date.now(), data });
  while (entries.size > MAX_ENTRIES) entries.delete(entries.keys().next().value);
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
    .then((data) => writeEcommerceAdminCache(scope, resource, data))
    .finally(() => {
      if (requests.get(key) === request) requests.delete(key);
    });
  requests.set(key, request);
  return request;
}

export function clearEcommerceAdminCache(scope, resourcePrefix = "") {
  const scopePrefix = scope == null ? null : `${encodeURIComponent(String(scope || "authenticated"))}::`;
  [...entries.keys(), ...requests.keys()].forEach((key) => {
    const belongsToScope = scopePrefix == null || key.startsWith(scopePrefix);
    const resource = key.slice(key.indexOf("::") + 2);
    if (belongsToScope && resource.startsWith(resourcePrefix)) {
      entries.delete(key);
      requests.delete(key);
    }
  });
}
