import { apiFetch, getApiUrl, readApiResponse, createApiError } from "../utils/apiClient";
async function request(course, lesson, block, suffix = "", body, learner = false) {
  const path = `/elearning/${learner ? "my-learning/" : ""}courses/${encodeURIComponent(course)}${lesson ? `/lessons/${encodeURIComponent(lesson)}` : ""}/assessments${block ? `/${encodeURIComponent(block)}` : ""}${suffix}`;
  const response = await apiFetch(getApiUrl(path), body === undefined ? { cache: "no-store" } : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}
export const loadAssessment = (c, l, b, preview = false) => request(c, l, b, preview ? "/preview" : "");
export const createAssessment = (c, l, body) => request(c, l, null, "", body);
export const commandAssessment = (c, l, b, body) => request(c, l, b, "/commands", body);
export const learnerAssessment = (c, l, b) => request(c, l, b, "", undefined, true);
export const startAssessment = (c, l, b) => request(c, l, b, "/attempts", {}, true);
export const submitAssessment = (c, l, b, attempt, answers) => request(c, l, b, `/attempts/${encodeURIComponent(attempt)}/submission`, { answers }, true);

export const fetchPlacements = (course, section) => request(course, null, null, section ? `?section_id=${encodeURIComponent(section)}` : "");
export const attachAssessment = (course, body) => request(course, null, null, "/attach", body);
export const placementCommand = (course, placement, body) => request(course, null, placement, "/placement", body);
