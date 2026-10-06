import { apiFetch, getApiUrl, readApiResponse, createApiError } from "../utils/apiClient";

export async function fetchCourseProgress(courseId) {
  const response = await apiFetch(getApiUrl(`/elearning/courses/${encodeURIComponent(courseId)}/progress`), { cache: "no-store" });
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}

async function enrollmentRequest(courseId, path, options) {
  const response = await apiFetch(getApiUrl(`/elearning/courses/${encodeURIComponent(courseId)}${path}`), options);
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}
const command = (payload) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
export const fetchCourseEnrollments = (courseId) => enrollmentRequest(courseId, "/enrollments", { cache: "no-store" });
export const fetchEnrollmentCandidates = (courseId, query = "", offset = 0) => enrollmentRequest(courseId, `/enrollment-candidates?query=${encodeURIComponent(query)}&limit=50&offset=${offset}`, { cache: "no-store" });
export const enrollCourseUsers = (courseId, userIds, accessSource) => enrollmentRequest(courseId, "/enrollments/users", command({ user_ids: userIds, access_source: accessSource }));
export const changeEnrollmentStatus = (courseId, enrollment, action) => enrollmentRequest(courseId, `/enrollments/${encodeURIComponent(enrollment.id)}/status`, command({ action, expected_status: enrollment.enrollment_status, confirmed: action !== "reactivate" }));
