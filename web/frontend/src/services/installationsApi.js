import {
  apiFetch,
  getApiUrl,
  readApiError,
  readApiResponse,
} from "../utils/apiClient";

async function installationRequest(path, init, fallback) {
  const response = await apiFetch(getApiUrl(path), init);
  const data = await readApiResponse(response);
  if (!response.ok) throw new Error(readApiError(data, fallback));
  return data;
}

export async function listInstallations(currentInstallationId) {
  const params = new URLSearchParams();
  if (currentInstallationId) {
    params.set("current_installation_id", currentInstallationId);
  }
  const suffix = params.size ? `?${params.toString()}` : "";
  const data = await installationRequest(
    `/installations${suffix}`,
    { method: "GET", cache: "no-store" },
    "Could not load devices."
  );
  return Array.isArray(data.installations) ? data.installations : [];
}

export async function revokeInstallation(installationRecordId) {
  return installationRequest(
    `/installations/${encodeURIComponent(installationRecordId)}`,
    { method: "DELETE", headers: { "Content-Type": "application/json" } },
    "Could not remove device."
  );
}

export async function disableCurrentInstallationNotifications(installationId) {
  return installationRequest(
    "/installations/current/notifications/disable",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ installation_id: installationId }),
    },
    "Could not disable notifications."
  );
}
