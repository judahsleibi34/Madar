import {
  apiFetch,
  createApiError,
  getApiUrl,
  readApiError,
  readApiResponse,
} from "../utils/apiClient";
import {
  clearAllEcommerceCatalogCaches,
  clearEcommerceThemeCache,
  getOrCreateEcommerceCatalogRequest,
  getOrCreateEcommerceThemeRequest,
  readEcommerceCatalogCache,
  readEcommerceThemeCache,
  removeFromEcommerceCatalogCache,
  updateEcommerceCatalogCache,
  writeEcommerceThemeCache,
} from "../components/DashboardBuilder/utils/ecommerceCatalogCache";
import {
  clearEcommerceAdminCache,
  loadEcommerceAdminResource,
  writeEcommerceAdminCache,
} from "../components/DashboardBuilder/utils/ecommerceAdminCache";

async function request(path, options = {}) {
  const response = await apiFetch(getApiUrl(path), {
    cache: "no-store",
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });

  if (response.status === 204) return null;
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data, "Catalog request failed");
  return data;
}

let catalogOptionsPreload = null;

export const preloadEcommerceCatalogOptions = () => {
  if (!catalogOptionsPreload) {
    // This GET authorizes independently on the backend. Do not let a
    // speculative 401 start its own refresh while auth bootstrap is running.
    catalogOptionsPreload = request("/ecommerce/catalog/options", {
      skipAuthRefresh: true,
    });
    // The route may redirect before consuming the speculative request.
    catalogOptionsPreload.catch(() => {});
  }
  return catalogOptionsPreload;
};

export const clearEcommerceCatalogOptionsPreload = () => {
  catalogOptionsPreload = null;
};

const loadEcommerceCatalogOptions = async () => {
  const preloaded = catalogOptionsPreload;
  catalogOptionsPreload = null;
  if (!preloaded) return request("/ecommerce/catalog/options");
  try {
    return await preloaded;
  } catch (error) {
    // Auth bootstrap may have refreshed an expired session in parallel.
    // Retry through the normal request path only after the protected route mounts.
    if (error?.status === 401 || error?.status === 403) {
      return request("/ecommerce/catalog/options");
    }
    throw error;
  }
};

export const fetchEcommerceCatalog = ({ scope, force = false } = {}) => {
  if (!force) {
    const cached = readEcommerceCatalogCache(scope);
    if (cached) return Promise.resolve(cached);
  }

  return getOrCreateEcommerceCatalogRequest(scope, async () => {
    const catalog = await request("/ecommerce/catalog");
    return catalog;
  });
};

export const fetchEcommerceCatalogSection = (section, { scope, force = false } = {}) => {
  if (!["tags", "categories", "brands", "products"].includes(section)) {
    return Promise.reject(new Error("Unsupported ecommerce catalog section"));
  }
  return loadEcommerceAdminResource(
    scope,
    `catalog:${section}`,
    () => request(`/ecommerce/${section}`),
    { force },
  );
};

export const fetchEcommerceCatalogOptions = ({ scope, force = false } = {}) =>
  loadEcommerceAdminResource(
    scope,
    "catalog:options",
    loadEcommerceCatalogOptions,
    { force },
  );

export const saveEcommerceItem = async (section, itemId, payload, { scope } = {}) => {
  const result = await request(`/ecommerce/${section}${itemId ? `/${itemId}` : ""}`, {
    method: itemId ? "PUT" : "POST",
    body: JSON.stringify(payload),
  });
  const singular = section === "categories" ? "category" : section === "products" ? "product" : section === "brands" ? "brand" : "tag";
  updateEcommerceCatalogCache(scope, section, result?.[singular]);
  clearEcommerceAdminCache(scope, `catalog:${section}`);
  if (section !== "products") clearEcommerceAdminCache(scope, "catalog:options");
  return result;
};

export const saveEcommerceProductVariants = async (productId, payload, { scope } = {}) => {
  const result = await request(`/ecommerce/products/${productId}/variants`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  updateEcommerceCatalogCache(scope, "products", result?.product);
  clearEcommerceAdminCache(scope, "catalog:products");
  return result;
};

export const deleteEcommerceItem = async (section, itemId, { scope } = {}) => {
  const result = await request(`/ecommerce/${section}/${itemId}`, { method: "DELETE" });
  removeFromEcommerceCatalogCache(scope, section, itemId);
  clearEcommerceAdminCache(scope, `catalog:${section}`);
  if (section !== "products") clearEcommerceAdminCache(scope, "catalog:options");
  return result;
};

export const fetchEcommerceTheme = ({ scope, force = false } = {}) => {
  if (!force) {
    const cached = readEcommerceThemeCache(scope);
    if (cached) return Promise.resolve({ theme: cached });
  }
  return getOrCreateEcommerceThemeRequest(scope, async () => {
    const result = await request("/ecommerce/theme");
    return result;
  });
};

export const saveEcommerceTheme = async (theme, { scope } = {}) => {
  const result = await request("/ecommerce/theme", {
    method: "PUT",
    body: JSON.stringify(theme),
  });
  clearEcommerceThemeCache(scope);
  writeEcommerceThemeCache(scope, result?.theme || theme);
  return result;
};

export const fetchEcommerceGrowth = () => request("/ecommerce/growth");

export const saveEcommerceGrowth = (growth) => request("/ecommerce/growth", {
  method: "PUT",
  body: JSON.stringify(growth),
});

export const fetchEcommerceLandingPage = () => request("/ecommerce/landing-page");

export const saveEcommerceLandingPage = (landingPage) => request("/ecommerce/landing-page", {
  method: "PUT",
  body: JSON.stringify(landingPage),
});

export const fetchEcommerceSocialLinks = ({ scope, force = false } = {}) =>
  loadEcommerceAdminResource(scope, "social-links", () => request("/ecommerce/social-links"), { force });

export const saveEcommerceSocialLinks = async (socialLinks, { scope } = {}) => {
  const result = await request("/ecommerce/social-links", {
    method: "PUT",
    body: JSON.stringify(socialLinks),
  });
  clearEcommerceAdminCache(scope, "social-links");
  writeEcommerceAdminCache(scope, "social-links", result);
  return result;
};

export const fetchEcommerceSettings = ({ scope, force = false } = {}) => loadEcommerceAdminResource(scope, "settings", () => request("/ecommerce/settings"), { force });

export const saveEcommerceSettings = async (currency, { scope } = {}) => {
  const result = await request("/ecommerce/settings", { method: "PUT", body: JSON.stringify({ currency }) });
  clearEcommerceAdminCache(scope, "settings");
  writeEcommerceAdminCache(scope, "settings", result);
  clearAllEcommerceCatalogCaches();
  return result;
};

export const fetchEcommerceDeliveryAreas = ({ scope, force = false } = {}) =>
  loadEcommerceAdminResource(scope, "delivery-areas", () => request("/ecommerce/delivery-areas"), { force });

export const createEcommerceDeliveryLocation = async (location, { scope } = {}) => {
  const result = await request("/ecommerce/delivery-areas/custom", {
    method: "POST",
    body: JSON.stringify(location),
  });
  clearEcommerceAdminCache(scope, "delivery-areas");
  if (Array.isArray(result?.areas)) writeEcommerceAdminCache(scope, "delivery-areas", result);
  return result;
};

export const deleteEcommerceDeliveryLocation = async (areaId, { scope } = {}) => {
  const result = await request(`/ecommerce/delivery-areas/custom/${encodeURIComponent(areaId)}`, {
    method: "DELETE",
  });
  clearEcommerceAdminCache(scope, "delivery-areas");
  clearEcommerceAdminCache(scope, "delivery-pricing");
  return result;
};

export const saveEcommerceDeliveryAreas = async (enabledServiceAreaIds, { scope } = {}) => {
  const result = await request("/ecommerce/delivery-areas", {
    method: "PUT",
    body: JSON.stringify({ enabled_service_area_ids: enabledServiceAreaIds }),
  });
  clearEcommerceAdminCache(scope, "delivery-areas");
  if (Array.isArray(result?.areas)) writeEcommerceAdminCache(scope, "delivery-areas", result);
  return result;
};

export const fetchEcommerceDeliveryPricing = ({ scope, force = false } = {}) =>
  loadEcommerceAdminResource(scope, "delivery-pricing", () => request("/ecommerce/delivery-pricing"), { force });

export const saveEcommerceDeliveryPricing = async (prices, { scope } = {}) => {
  const result = await request("/ecommerce/delivery-pricing", {
    method: "PUT",
    body: JSON.stringify({ prices }),
  });
  clearEcommerceAdminCache(scope, "delivery-pricing");
  if (result?.pricing) writeEcommerceAdminCache(scope, "delivery-pricing", result);
  return result;
};

export const fetchEcommerceOrders = (filters = {}, { scope, force = false } = {}) => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") params.set(key, String(value));
  });
  const path = `/ecommerce/orders${params.toString() ? `?${params}` : ""}`;
  return loadEcommerceAdminResource(scope, `orders:${path}`, () => request(path), { force });
};

export const fetchEcommerceOrder = (orderId, { scope, force = false } = {}) => {
  const path = `/ecommerce/orders/${encodeURIComponent(orderId)}`;
  return loadEcommerceAdminResource(scope, `order:${orderId}`, () => request(path), { force });
};

export const transitionEcommerceOrder = async (orderId, status, note = "", idempotencyKey = globalThis.crypto?.randomUUID?.()) => {
  const result = await request(`/ecommerce/orders/${encodeURIComponent(orderId)}/status`, {
    method: "POST",
    body: JSON.stringify({ status, note, idempotency_key: idempotencyKey || `status-${Date.now()}-${Math.random().toString(36).slice(2)}` }),
  });
  clearEcommerceAdminCache(null, "order");
  return result;
};

export const collectEcommerceOrderPayment = async (orderId) => {
  const result = await request(`/ecommerce/orders/${encodeURIComponent(orderId)}/collect-payment`, { method: "POST" });
  clearEcommerceAdminCache(null, "order");
  return result;
};

export const fetchEcommerceLoyalty = ({ scope, force = false } = {}) =>
  loadEcommerceAdminResource(scope, "loyalty", () => request("/ecommerce/loyalty"), { force });

export const saveEcommerceLoyalty = async (payload, { scope } = {}) => {
  const result = await request("/ecommerce/loyalty", { method: "PUT", body: JSON.stringify(payload) });
  clearEcommerceAdminCache(scope, "loyalty");
  writeEcommerceAdminCache(scope, "loyalty", result);
  return result;
};

export const revokeEcommerceLoyaltyEntitlement = (entitlementId) => request(`/ecommerce/loyalty/entitlements/${encodeURIComponent(entitlementId)}/revoke`, { method: "POST" });

export const uploadEcommerceProductImage = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiFetch(getApiUrl("/ecommerce/product-media/upload"), {
    method: "POST",
    body: formData,
  });
  const data = await readApiResponse(response);
  if (!response.ok) {
    throw createApiError(response, data, "Could not upload this product media");
  }
  return data?.asset_url || data?.url || "";
};


const PUBLIC_STORE_FRESH_MS = 60_000;
const PUBLIC_STORE_STALE_MS = 30 * 60_000;
const PUBLIC_STORE_MAX_ENTRIES = 80;
const PUBLIC_STORE_STORAGE_KEY = "madar-public-store-cache-v2";

const readStoredPublicStoreResponses = () => {
  try {
    const stored = JSON.parse(globalThis.sessionStorage?.getItem(PUBLIC_STORE_STORAGE_KEY) || "{}");
    return stored && typeof stored === "object" && !Array.isArray(stored) ? stored : {};
  } catch {
    return {};
  }
};

const writeStoredPublicStoreResponses = (entries) => {
  try {
    globalThis.sessionStorage?.setItem(PUBLIC_STORE_STORAGE_KEY, JSON.stringify(entries));
  } catch {
    // Memory caching remains available when session storage is unavailable.
  }
};
const publicStoreResponseCache = new Map();
const publicStoreRequests = new Map();

const rememberPublicStoreResponse = (url, data) => {
  publicStoreResponseCache.delete(url);
  publicStoreResponseCache.set(url, { data, storedAt: Date.now() });
  while (publicStoreResponseCache.size > PUBLIC_STORE_MAX_ENTRIES) {
    publicStoreResponseCache.delete(publicStoreResponseCache.keys().next().value);
  }
  const entries = readStoredPublicStoreResponses();
  entries[url] = { data, storedAt: Date.now() };
  Object.keys(entries)
    .sort((first, second) => Number(entries[second]?.storedAt || 0) - Number(entries[first]?.storedAt || 0))
    .slice(PUBLIC_STORE_MAX_ENTRIES)
    .forEach((oldUrl) => { delete entries[oldUrl]; });
  writeStoredPublicStoreResponses(entries);
  return data;
};

const readCachedPublicStoreResponse = (url) => {
  const memoryEntry = publicStoreResponseCache.get(url);
  if (memoryEntry) return memoryEntry;
  const storedEntry = readStoredPublicStoreResponses()[url];
  if (!storedEntry || Date.now() - Number(storedEntry.storedAt || 0) > PUBLIC_STORE_STALE_MS) return null;
  publicStoreResponseCache.set(url, storedEntry);
  return storedEntry;
};

const loadPublicStoreResponse = (url) => {
  const pending = publicStoreRequests.get(url);
  if (pending) return pending;
  const requestPromise = apiFetch(url, { method: "GET" })
    .then(async (response) => {
      const data = await readApiResponse(response);
      if (!response.ok) {
        throw new Error(readApiError(data, "Could not load the live store"));
      }
      return rememberPublicStoreResponse(url, data);
    })
    .finally(() => publicStoreRequests.delete(url));
  publicStoreRequests.set(url, requestPromise);
  return requestPromise;
};

const fetchPublicStoreResponse = (path) => {
  const url = getApiUrl(path);
  const cached = readCachedPublicStoreResponse(url);
  if (cached) {
    const age = Date.now() - cached.storedAt;
    if (age <= PUBLIC_STORE_FRESH_MS) return Promise.resolve(cached.data);
    if (age <= PUBLIC_STORE_STALE_MS) {
      loadPublicStoreResponse(url).catch(() => {});
      return Promise.resolve(cached.data);
    }
    publicStoreResponseCache.delete(url);
  }
  return loadPublicStoreResponse(url);
};

export const clearPublicEcommerceCache = () => {
  publicStoreResponseCache.clear();
  publicStoreRequests.clear();
  try { globalThis.sessionStorage?.removeItem(PUBLIC_STORE_STORAGE_KEY); } catch { /* no-op */ }
};

const publicStoreProfilePath = (subdomain) =>
  `/public/sites/${encodeURIComponent(subdomain)}/store-profile`;

const rememberEmbeddedStoreProfile = (subdomain, data) => {
  if (data?.site) {
    rememberPublicStoreResponse(getApiUrl(publicStoreProfilePath(subdomain)), {
      success: true,
      site: data.site,
    });
  }
  return data;
};

export const fetchPublicEcommerceProfile = (subdomain) =>
  fetchPublicStoreResponse(publicStoreProfilePath(subdomain));

export const fetchPublicEcommerceCatalog = async (subdomain, filters = {}) => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      params.set(key, String(value));
    }
  });
  const query = params.toString();
  const data = await fetchPublicStoreResponse(
    `/public/sites/${encodeURIComponent(subdomain)}/catalog${query ? `?${query}` : ""}`
  );
  return rememberEmbeddedStoreProfile(subdomain, data);
};

export const preloadPublicEcommerceCatalog = (subdomain) =>
  fetchPublicEcommerceCatalog(subdomain, { sort: "latest", page: "1", locale: "en", limit: "12" }).catch(() => null);

export const fetchPublicEcommerceProduct = async (subdomain, slug, locale = "en") => {
  const data = await fetchPublicStoreResponse(
    `/public/sites/${encodeURIComponent(subdomain)}/catalog/products/${encodeURIComponent(slug)}?locale=${encodeURIComponent(locale)}`
  );
  return rememberEmbeddedStoreProfile(subdomain, data);
};

export const reconcilePublicEcommerceCart = (subdomain, items) =>
  request(`/public/sites/${encodeURIComponent(subdomain)}/cart/reconcile`, {
    method: "POST",
    body: JSON.stringify({ items }),
  });

export const fetchPublicEcommerceDeliveryAreas = (subdomain) =>
  request(`/public/sites/${encodeURIComponent(subdomain)}/delivery-areas`);

export const fetchPublicEcommerceLoyalty = (subdomain) =>
  request(`/public/sites/${encodeURIComponent(subdomain)}/loyalty/me`);

export const fetchPublicStoreAccount = (subdomain) =>
  request(`/public/sites/${encodeURIComponent(subdomain)}/auth/status`);

export const loginPublicStoreAccount = (subdomain, payload) =>
  request(`/public/sites/${encodeURIComponent(subdomain)}/auth/login`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const registerPublicStoreAccount = (subdomain, payload) =>
  request(`/public/sites/${encodeURIComponent(subdomain)}/auth/register`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const logoutPublicStoreAccount = (subdomain) =>
  request(`/public/sites/${encodeURIComponent(subdomain)}/auth/logout`, {
    method: "POST",
  });

export const fetchPublicEcommerceDiscounts = (subdomain) =>
  request(`/public/sites/${encodeURIComponent(subdomain)}/discounts`);

export const fetchPublicEcommerceOrderConfirmation = (subdomain, token) =>
  request(`/public/sites/${encodeURIComponent(subdomain)}/orders/confirmation/${encodeURIComponent(token)}`);

export const createPublicEcommerceOrder = (subdomain, payload) =>
  request(`/public/sites/${encodeURIComponent(subdomain)}/orders`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
