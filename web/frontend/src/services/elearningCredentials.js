import { apiFetch, getApiUrl, readApiResponse, createApiError } from "../utils/apiClient";
async function request(path, method = "GET", payload) {
  const response = await apiFetch(getApiUrl(path), { method, cache: "no-store", ...(payload ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) } : {}) });
  const data = await readApiResponse(response);
  if (!response.ok) throw createApiError(response, data);
  return data;
}
export const certificatePath = (course) => `/elearning/courses/${encodeURIComponent(course)}/certificate`;
export const fetchCertificates = (course) => request(course ? certificatePath(course) : "/elearning/my-certificates");
export const saveCertificateTemplate = (form) => request(`/elearning/certificate-templates${form.id ? `/${encodeURIComponent(form.id)}` : ""}`, form.id ? "PUT" : "POST", { design: form.design, status: form.status, expected_revision: form.revision || 1 });
export const configureCertificate = (course, value) => request(certificatePath(course), "PUT", value);
export const backfillCertificates = (course) => request(`${certificatePath(course)}/backfill`, "POST", { confirmed: true });
export const revokeCertificate = (course, id, reason) => request(`${certificatePath(course)}/credentials/${encodeURIComponent(id)}/revocation`, "POST", { confirmed: true, reason });
export const credentialPath = (id, course) => course ? `${certificatePath(course)}/credentials/${encodeURIComponent(id)}` : `/elearning/my-certificates/${encodeURIComponent(id)}`;
export const fetchCredential = (id, course) => request(credentialPath(id, course));
export const verifyCredential = (token) => request(`/verify/credential/${encodeURIComponent(token)}`);
export async function downloadCredential(id, course) {
  const response = await apiFetch(getApiUrl(`${credentialPath(id, course)}?pdf=true`), { cache: "no-store" });
  if (!response.ok) throw createApiError(response, await readApiResponse(response));
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = "certificate.pdf"; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const CERTIFICATE_VARIABLES = ["learner_name", "course_name", "completion_date", "issue_date", "issuer_name", "credential_id"];
export function validatePlaceholders(design) {
  for (const value of Object.values(design)) {
    for (const match of value.matchAll(/\{\{\s*([^{}]+?)\s*\}\}/g)) if (!CERTIFICATE_VARIABLES.includes(match[1].trim())) return match[1].trim();
    if (/\{\{|\}\}/.test(value.replace(/\{\{\s*([^{}]+?)\s*\}\}/g, ""))) return value;
  }
  return null;
}
