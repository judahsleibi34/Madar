import { apiFetch, getApiUrl, readApiResponse, createApiError } from "../utils/apiClient";
async function request(path, payload) {
 const response = await apiFetch(getApiUrl(`/elearning/relationships${path}`), payload ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) } : { cache: "no-store" });
 const data = await readApiResponse(response); if (!response.ok) throw createApiError(response, data); return data;
}
export const fetchRelationships = (kind, id, query = "", offset = 0) => request(`/${kind}/${encodeURIComponent(id)}?member_query=${encodeURIComponent(query)}&member_offset=${offset}`);
export const changeRelationship = (kind, id, command) => request(`/${kind}/${encodeURIComponent(id)}/commands`, command);
export const fetchRelationshipCandidates = (kind, query = "", offset = 0) => request(`/candidates?kind=${kind}&query=${encodeURIComponent(query)}&offset=${offset}`);
export const fetchDirectorySummary = (kind) => request(`/directory-summary?kind=${kind}`);
