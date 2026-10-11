import { apiFetch, getApiUrl } from "../../utils/apiClient";
export async function request(path, payload) {
  const response = await apiFetch(getApiUrl(`/elearning/programmes${path}`), payload ? {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  } : { cache: "no-store" });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const error = new Error("Request unavailable. Refresh and try again.");
    error.code = body.detail?.code;
    throw error;
  }
  return response.json();
}
