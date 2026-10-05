import { apiFetch, getApiUrl, readApiResponse, createApiError } from "../utils/apiClient";
async function request(path, method = "GET", payload) {
  const response = await apiFetch(getApiUrl(`/elearning${path}`), { method, cache: "no-store", ...(payload ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) } : {}) });
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}
export const fetchPlans = () => request("/plans");
export const savePlan = (plan) => request(plan.id ? `/plans/${encodeURIComponent(plan.id)}` : "/plans", plan.id ? "PUT" : "POST", Object.fromEntries(Object.entries(plan).filter(([key]) => key !== "id")));
export const fetchCatalog = () => request("/catalog");
export const fetchMyPlans = () => request("/my-plans");
export const enrollCatalogCourse = (id) => request(`/catalog/${encodeURIComponent(id)}/enrollment`, "POST");
export const createCheckout = (offering, course, key) => request("/checkout", "POST", { offering_id: offering, course_id: course || null, idempotency_key: key });
export const localPaymentEvent = (id, state, cancel = false) => request(`/checkout/${encodeURIComponent(id)}/local-event`, "POST", { state, cancel_at_period_end: cancel });
