import { apiFetch, getApiUrl, readApiResponse, createApiError } from "../utils/apiClient";

async function request(courseId, lessonId, path, options) {
  const response = await apiFetch(getApiUrl(`/elearning/courses/${encodeURIComponent(courseId)}${lessonId ? `/lessons/${encodeURIComponent(lessonId)}/content` : "/assessments"}${path}`), options);
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}
export const fetchContent = (courseId, lessonId) => request(courseId, lessonId, "", { cache: "no-store" });
export const executeContentCommand = (courseId, lessonId, command) => request(courseId, lessonId, "/commands", {
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(command),
});
export const uploadContentMedia = (courseId, lessonId, file) => {
  const body = new FormData(); body.append("file", file);
  return request(courseId, lessonId, "/media/upload", { method: "POST", body });
};
export const fetchAudioMedia = (courseId, lessonId) => request(courseId, lessonId, "/media/audio", { cache: "no-store" });
