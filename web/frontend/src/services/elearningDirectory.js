import { apiFetch, getApiUrl, readApiResponse, createApiError } from "../utils/apiClient";

async function request(kind, path, options) {
  if (!["groups", "instructors"].includes(kind)) throw new Error("Unknown E-Learning directory");
  const response = await apiFetch(getApiUrl(`/elearning/${kind}${path}`), options);
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}
const json = (method, payload) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
export const fetchDirectory = (kind, offset = 0) => request(kind, `?limit=50&offset=${offset}`, { cache: "no-store" });
export const createDirectoryItem = (kind, payload) => request(kind, "", json("POST", payload));
export const updateDirectoryItem = (kind, id, payload) => request(kind, `/${encodeURIComponent(id)}`, json("PUT", payload));
export const archiveDirectoryItem = (kind, item) => request(kind, `/${encodeURIComponent(item.id)}/archive`, json("POST", { expected_revision: item.revision }));
export const deleteGroup = (item) => request("groups", `/${encodeURIComponent(item.id)}`, json("DELETE", { expected_revision: item.revision, confirmed: true }));
export const deleteDirectoryItem = (kind, item) => request(kind, `/${encodeURIComponent(item.id)}`, json("DELETE", { expected_revision: item.revision, confirmed: true }));
