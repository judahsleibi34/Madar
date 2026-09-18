export const DASHBOARD_CACHE_VERSION = 1;

const STORAGE_KEY = `madar-dashboard-cache-v${DASHBOARD_CACHE_VERSION}`;
const MAX_AGE_MS = 24 * 60 * 60 * 1000;
const MAX_ENTRIES = 18;
const memoryCache = new Map();
const metricsRequests = new Map();
const METRICS_FRESH_MS = 30_000;
let cacheGeneration = 0;

export function getDashboardCacheScope(user) {
  const tenantId = user?.tenant_id ?? user?.tenantId;
  const userId = user?.id ?? user?.auth_id ?? user?.email;
  if (tenantId === undefined || tenantId === null || !userId) return "";
  return `tenant:${encodeURIComponent(String(tenantId))}:user:${encodeURIComponent(String(userId))}`;
}

function readEntries() {
  try {
    const entries = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) || "{}");
    return entries && typeof entries === "object" && !Array.isArray(entries) ? entries : {};
  } catch {
    return {};
  }
}

function writeEntries(entries) {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Memory cache remains available when session storage is unavailable.
  }
}

function read(key) {
  if (!key) return null;
  let entry = memoryCache.get(key);
  if (!entry) entry = readEntries()[key];
  if (!entry || Date.now() - Number(entry.cachedAt) > MAX_AGE_MS) return null;
  memoryCache.set(key, entry);
  return entry.value ?? null;
}

function write(key, value) {
  if (!key || !value || typeof value !== "object") return;
  const entry = { value, cachedAt: Date.now() };
  memoryCache.set(key, entry);
  const entries = readEntries();
  entries[key] = entry;
  Object.keys(entries)
    .sort((a, b) => Number(entries[b]?.cachedAt || 0) - Number(entries[a]?.cachedAt || 0))
    .slice(MAX_ENTRIES)
    .forEach((oldKey) => delete entries[oldKey]);
  writeEntries(entries);
}

export const readDashboardMetricsCache = (scope) =>
  scope ? read(`metrics:${scope}`) : null;

export const writeDashboardMetricsCache = (scope, metrics) => {
  if (scope) write(`metrics:${scope}`, metrics);
};

export const readScreenTimeCache = (scope, projectId, period) =>
  scope
    ? read(
        `screen-time:${scope}:project:${encodeURIComponent(
          String(projectId || "all"),
        )}:period:${period}`,
      )
    : null;

export const writeScreenTimeCache = (scope, projectId, period, summary) => {
  if (!scope) return;
  write(
    `screen-time:${scope}:project:${encodeURIComponent(
      String(projectId || "all"),
    )}:period:${period}`,
    summary,
  );
};

// A short freshness window avoids repeated reads during dashboard navigation.
// Older snapshots remain visible while the caller refreshes in the background.
export function fetchDashboardMetricsCached(scope, loader) {
  if (!scope) return Promise.resolve().then(loader);
  const key = `metrics:${scope}`;
  const snapshot = readDashboardMetricsCache(scope);
  const entry = memoryCache.get(key);
  if (snapshot && entry && Date.now() - entry.cachedAt < METRICS_FRESH_MS) {
    return Promise.resolve(snapshot);
  }
  if (metricsRequests.has(scope)) return metricsRequests.get(scope);
  const generation = cacheGeneration;
  const request = Promise.resolve().then(loader).then(metrics => {
    if (generation === cacheGeneration && metricsRequests.get(scope) === request) {
      writeDashboardMetricsCache(scope, metrics);
    }
    return metrics;
  }).finally(() => {
    if (metricsRequests.get(scope) === request) metricsRequests.delete(scope);
  });
  metricsRequests.set(scope, request);
  return request;
}

export function clearAllDashboardSnapshotCaches() {
  cacheGeneration += 1;
  memoryCache.clear();
  metricsRequests.clear();
  try { window.sessionStorage.removeItem(STORAGE_KEY); } catch { /* Memory cleanup still applies. */ }
}
