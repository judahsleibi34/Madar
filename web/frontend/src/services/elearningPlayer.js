import { apiFetch, getApiUrl, readApiResponse, createApiError } from "../utils/apiClient";
async function request(path = "", method = "GET") {
  const response = await apiFetch(getApiUrl(`/elearning/my-learning${path}`), { method, cache: "no-store" });
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}
export const fetchMyLearning = (offset = 0) => request(`?offset=${offset}`);
export const fetchLearningCourse = (course) => request(`/courses/${encodeURIComponent(course)}`);
export const fetchLearningLesson = (course, lesson) => request(`/courses/${encodeURIComponent(course)}/lessons/${encodeURIComponent(lesson)}`);
export const completeLearningLesson = (course, lesson) => request(`/courses/${encodeURIComponent(course)}/lessons/${encodeURIComponent(lesson)}/completion`, "POST");
