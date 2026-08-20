import {
  apiFetch,
  getApiUrl,
  readApiError,
  readApiResponse,
} from "../utils/apiClient";
import {
  clearEcommerceCatalogCache,
  getOrCreateEcommerceCatalogRequest,
  readEcommerceCatalogCache,
  writeEcommerceCatalogCache,
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
  clearEcommerceCatalogCache(scope);
  return result;
};

export const deleteEcommerceItem = async (section, itemId, { scope } = {}) => {
  const result = await request(`/ecommerce/${section}/${itemId}`, { method: "DELETE" });
  clearEcommerceCatalogCache(scope);
  return result;
};

export const fetchPublicEcommerceCatalog = async (subdomain, filters = {}) => {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      params.set(key, String(value));
    }
  });
  const query = params.toString();
  const response = await apiFetch(
    getApiUrl(`/public/sites/${encodeURIComponent(subdomain)}/catalog${query ? `?${query}` : ""}`),
    { method: "GET" }
  );
  const data = await readApiResponse(response);
  if (!response.ok) {
    throw new Error(readApiError(data, "Could not load the live store"));
  }
  return data;
};

export const fetchPublicEcommerceProduct = async (subdomain, slug, locale = "en") => {
  const response = await apiFetch(
    getApiUrl(
      `/public/sites/${encodeURIComponent(subdomain)}/catalog/products/${encodeURIComponent(slug)}?locale=${encodeURIComponent(locale)}`
    ),
    { method: "GET" }
  );
  const data = await readApiResponse(response);
  if (!response.ok) {
    throw new Error(readApiError(data, "Could not load this product"));
  }
  return data;
};
