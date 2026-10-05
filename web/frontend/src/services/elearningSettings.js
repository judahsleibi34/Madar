import { apiFetch, getApiUrl, readApiResponse, createApiError } from "../utils/apiClient";

export async function fetchELearningSettings() {
  const response = await apiFetch(getApiUrl("/elearning/settings"), { cache: "no-store" });
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}

export async function saveELearningSettings(settings) {
  const response = await apiFetch(getApiUrl("/elearning/settings"), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}

export async function uploadELearningLogo(file) {
  const body = new FormData();
  body.append("file", file);
  const response = await apiFetch(getApiUrl("/elearning/logo/upload"), { method: "POST", body });
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}
