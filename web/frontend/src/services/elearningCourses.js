import { apiFetch, getApiUrl, readApiResponse, createApiError } from "../utils/apiClient";

async function request(path, options) {
  const response = await apiFetch(getApiUrl(`/elearning/courses${path}`), options);
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}
const json = (method, payload) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
export const fetchCourses = (offset = 0) => request(`?limit=50&offset=${offset}`, { cache: "no-store" });
export const fetchCourse = (id) => request(`/${encodeURIComponent(id)}`, { cache: "no-store" });
export const createCourse = (payload) => request("", json("POST", payload));
export const updateCourse = (id, payload) => request(`/${encodeURIComponent(id)}`, json("PUT", payload));
export const duplicateCourse = (course) => request(`/${encodeURIComponent(course.id)}/duplicate`, json("POST", { expected_revision: course.revision }));
export const archiveCourse = (course) => request(`/${encodeURIComponent(course.id)}/archive`, json("POST", { expected_revision: course.revision }));
export const uploadCourseCover = (file) => {
  const body = new FormData(); body.append("file", file);
  return request("/cover/upload", { method: "POST", body });
};

export const deleteCourse = (course, confirmationName) => request(`/${encodeURIComponent(course.id)}`, json("DELETE", { expected_revision: course.revision, expected_structure_revision: course.structure_revision || 1, confirmation_name: confirmationName, confirmed: true }));
