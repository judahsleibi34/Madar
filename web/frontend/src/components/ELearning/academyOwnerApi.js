import { apiFetch, getApiUrl } from "../../utils/apiClient";
export async function academyOwnerApi(path, { method = "GET", body, file, download = false } = {}) {
  const form = file ? new FormData() : null;
  if (form) form.append("file", file);
  const response = await apiFetch(getApiUrl(`/elearning/owner${path}`), { method, cache: "no-store", ...(form ? { body: form } : body ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}) });
  if (!response.ok) { const body = await response.json().catch(() => ({})); const error = new Error("Academy request unavailable"); error.code = body.detail?.code; throw error; }
  if (download) {
    const url = URL.createObjectURL(await response.blob());
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = download; anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);return null;
  }
  return response.json();
}
