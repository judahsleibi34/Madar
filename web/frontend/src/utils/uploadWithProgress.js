import { CSRF_HEADER_NAME, getApiUrl, getCsrfToken } from "./apiClient";

/**
 * POST one file with upload progress (0-100). If the session or CSRF token
 * needs refreshing (401/403), `fallback` (the normal apiFetch upload, which
 * refreshes them) is used once instead, without progress.
 */
export function uploadWithProgress(path, file, { onProgress, fallback } = {}) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    const body = new FormData(); body.append("file", file);
    request.open("POST", getApiUrl(path));
    request.withCredentials = true;
    const token = getCsrfToken();
    if (token) request.setRequestHeader(CSRF_HEADER_NAME, token);
    request.upload.onprogress = event => { if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100)); };
    request.onerror = () => reject(new Error("Upload failed"));
    request.onload = () => {
      if ((request.status === 401 || request.status === 403) && fallback) { fallback(file).then(resolve, reject); return; }
      let data = null; try { data = JSON.parse(request.responseText); } catch { /* Non-JSON error page. */ }
      if (request.status >= 200 && request.status < 300 && data) { onProgress?.(100); resolve(data); return; }
      const error = new Error(data?.detail?.message || data?.detail || "Upload failed"); error.status = request.status; reject(error);
    };
    request.send(body);
  });
}
