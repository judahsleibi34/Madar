import {
  apiFetch,
  getApiUrl,
  readApiError,
  readApiResponse,
} from "../utils/apiClient";
import {
  getOrCreateEcommerceCatalogRequest,
  getOrCreateEcommerceThemeRequest,
  readEcommerceCatalogCache,
  readEcommerceThemeCache,
  removeFromEcommerceCatalogCache,
  updateEcommerceCatalogCache,
  writeEcommerceCatalogCache,
  writeEcommerceThemeCache,
} from "../components/DashboardBuilder/utils/ecommerceCatalogCache";

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
  if (!response.ok) throw new Error(readApiError(data, "Catalog request failed"));
  return data;
}

export const fetchEcommerceCatalog = ({ scope, force = false } = {}) => {
  if (!force) {
    const cached = readEcommerceCatalogCache(scope);
    if (cached) return Promise.resolve(cached);
  }

  return getOrCreateEcommerceCatalogRequest(scope, async () => {
    const catalog = await request("/ecommerce/catalog");
    writeEcommerceCatalogCache(scope, catalog);
    return catalog;
  });
};

export const saveEcommerceItem = async (section, itemId, payload, { scope } = {}) => {
  const result = await request(`/ecommerce/${section}${itemId ? `/${itemId}` : ""}`, {
    method: itemId ? "PUT" : "POST",
    body: JSON.stringify(payload),
  });
  const singular = section === "categories" ? "category" : section === "products" ? "product" : "tag";
  updateEcommerceCatalogCache(scope, section, result?.[singular]);
  return result;
};

export const deleteEcommerceItem = async (section, itemId, { scope } = {}) => {
  const result = await request(`/ecommerce/${section}/${itemId}`, { method: "DELETE" });
  removeFromEcommerceCatalogCache(scope, section, itemId);
  return result;
};

export const fetchEcommerceTheme = ({ scope, force = false } = {}) => {
  if (!force) {
    const cached = readEcommerceThemeCache(scope);
    if (cached) return Promise.resolve({ theme: cached });
  }
  return getOrCreateEcommerceThemeRequest(scope, async () => {
    const result = await request("/ecommerce/theme");
    writeEcommerceThemeCache(scope, result?.theme);
    return result;
  });
};

export const saveEcommerceTheme = async (theme, { scope } = {}) => {
  const result = await request("/ecommerce/theme", {
    method: "PUT",
    body: JSON.stringify(theme),
  });
  writeEcommerceThemeCache(scope, result?.theme || theme);
  return result;
};
export const uploadEcommerceProductImage = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiFetch(getApiUrl("/builder/assets/upload"), {
    method: "POST",
    body: formData,
  });
  const data = await readApiResponse(response);
  if (!response.ok) {
    throw new Error(readApiError(data, "Could not upload this product image"));
  }
  return data?.asset_url || data?.url || "";
};


const PUBLIC_STORE_FRESH_MS = 60_000;
const PUBLIC_STORE_STALE_MS = 5 * 60_000;
const PUBLIC_STORE_MAX_ENTRIES = 80;
const publicStoreResponseCache = new Map();
const publicStoreRequests = new Map();

const rememberPublicStoreResponse = (url, data) => {
  publicStoreResponseCache.delete(url);
  publicStoreResponseCache.set(url, { data, storedAt: Date.now() });
  while (publicStoreResponseCache.size > PUBLIC_STORE_MAX_ENTRIES) {
    publicStoreResponseCache.delete(publicStoreResponseCache.keys().next().value);
  }
  return data;
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
  const cached = publicStoreResponseCache.get(url);
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

export const fetchPublicEcommerceProduct = async (subdomain, slug, locale = "en") => {
  const data = await fetchPublicStoreResponse(
    `/public/sites/${encodeURIComponent(subdomain)}/catalog/products/${encodeURIComponent(slug)}?locale=${encodeURIComponent(locale)}`
  );
  return rememberEmbeddedStoreProfile(subdomain, data);
};
