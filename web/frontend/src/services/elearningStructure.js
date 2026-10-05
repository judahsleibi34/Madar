import { apiFetch, getApiUrl, readApiResponse, createApiError } from "../utils/apiClient";

async function request(courseId, path, options) {
  const response = await apiFetch(getApiUrl(`/elearning/courses/${encodeURIComponent(courseId)}${path}`), options);
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}
export const fetchStructure = (courseId) => request(courseId, "/structure", { cache: "no-store" });
export const fetchLesson = (courseId, lessonId) => request(courseId, `/lessons/${encodeURIComponent(lessonId)}`, { cache: "no-store" });
export const executeStructureCommand = (courseId, command) => request(courseId, "/structure/commands", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(command),
});
