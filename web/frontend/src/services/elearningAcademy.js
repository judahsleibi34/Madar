import { BUILDER_CLIENT_CONTRACT } from "../components/PageBuilder/services/PageBuilder.api";
import { apiFetch, getApiUrl, readApiResponse, createApiError } from "../utils/apiClient";
export async function fetchAcademy(identifier, courseId) {
  const path = `/public/academies/${encodeURIComponent(identifier)}${courseId ? `/courses/${encodeURIComponent(courseId)}` : ""}`;
  const response = await apiFetch(getApiUrl(path), { cache: "no-store" });
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}

export function academyReturnPath(requested, base, origin, allowLearning = false) {
  if (typeof requested !== "string" || !requested.startsWith("/") || requested.startsWith("//") || /[\\\r\n]/.test(requested)) return base;
  try {
    let decoded = requested;
    for (let i = 0; i < 4; i += 1) decoded = decodeURIComponent(decoded);
    if (/[\\\r\n]/.test(decoded) || decoded.startsWith("//") || new URL(decoded, origin).pathname.split("/").some(segment => segment === "." || segment === "..") || /(?:^|\/)\.\.?(?:\/|$)/.test(decoded.split(/[?#]/)[0])) return base;
    const url = new URL(requested, origin);
    if (url.origin === origin && (url.pathname === base || url.pathname.startsWith(`${base}/`) || (allowLearning && (url.pathname === "/my-learning" || url.pathname.startsWith("/my-learning/"))))) {
      return `${url.pathname}${url.search}${url.hash}`;
    }
  } catch { /* Invalid return locations resume at the academy home. */ }
  return base;
}

export async function initializeAcademyLanding() {
  const response = await apiFetch(getApiUrl("/public/academies/management/landing"), { method: "POST", headers: { "X-Madar-Builder-Contract": BUILDER_CLIENT_CONTRACT } });
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data.project;
}

async function academyAuth(identifier, action, payload) {
  const response = await apiFetch(getApiUrl(`/public/academies/${encodeURIComponent(identifier)}/auth/${action}`), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}
export const loginAcademy = (identifier, payload) => academyAuth(identifier, "login", payload);
export const registerAcademy = (identifier, payload) => academyAuth(identifier, "register", payload);
