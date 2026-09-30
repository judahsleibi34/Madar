import { apiFetch, getApiUrl, readApiError, readApiErrorCode } from "../utils/apiClient";

export async function commercialRequest(path, body) {
  const response = await apiFetch(getApiUrl(`/admin/billing/${path}`), {
    cache: "no-store",
    ...(body !== undefined ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}),
  });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(readApiError(data, "Commercial service unavailable."));
    error.code = readApiErrorCode(data);
    error.status = response.status;
    throw error;
  }
  return data;
}

export const moduleNames = { forms: "Madar Forms", website: "Madar Website", ecommerce: "Madar Commerce" };
export function money(minor, currency = "USD") {
  return Number.isInteger(minor) ? new Intl.NumberFormat("en", { style: "currency", currency }).format(minor / 100) : "Unavailable";
}
export function date(value) {
  if (!value || Number.isNaN(new Date(value).getTime())) return "Unavailable";
  return new Date(value).toLocaleString();
}
