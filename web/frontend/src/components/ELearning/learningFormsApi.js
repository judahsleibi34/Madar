import { apiFetch, getApiUrl, createApiError } from "../../utils/apiClient";
export async function learningFormsApi(path = "", options = {}) {
  const response = await apiFetch(getApiUrl(`/elearning/forms${path}`), {cache:"no-store", ...options, headers:options.body ? {"Content-Type":"application/json"} : undefined, body:options.body ? JSON.stringify(options.body) : undefined});
  if (options.download && response.ok) { const url = URL.createObjectURL(await response.blob());const a = document.createElement("a");a.href = url;a.download = options.download;a.click();setTimeout(() => URL.revokeObjectURL(url), 1000);return; }
  const data = await response.json();if (!response.ok) throw createApiError(response, data);return data;
}
