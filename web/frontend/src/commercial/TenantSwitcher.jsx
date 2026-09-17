import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiFetch, getApiUrl, getSelectedTenantId, readApiResponse, setSelectedTenantId } from "../utils/apiClient";
import { clearAllCalendarWorkspaceCaches } from "../components/DashboardBuilder/utils/calendarWorkspaceCache";
import { useWorkspaceCapabilities } from "./capabilityContext";

export default function TenantSwitcher({ user, onUserUpdated }) {
  const [tenants, setTenants] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { revalidate } = useWorkspaceCapabilities();
  const navigate = useNavigate();
  useEffect(() => {
    const controller = new AbortController();
    apiFetch(getApiUrl("/auth/tenants"), { cache: "no-store", signal: controller.signal })
      .then(async (response) => { const data = await readApiResponse(response); if (response.ok && !controller.signal.aborted) setTenants(data.tenants || []); })
      .catch(() => {});
    return () => controller.abort();
  }, [user?.id]);
  async function change(value) {
    const previous = getSelectedTenantId();
    setBusy(true); setError("");
    setSelectedTenantId(value);
    // Clear visible commercial context before any newly selected workspace data.
    revalidate();
    try {
      const response = await apiFetch(getApiUrl("/auth/user_status"), { cache: "no-store" });
      const data = await readApiResponse(response);
      if (!response.ok || !data.logged_in || Number(data.user?.tenant_id) !== Number(value)) throw new Error("Workspace access could not be verified.");
      clearAllCalendarWorkspaceCaches();
      onUserUpdated(data.user);
      navigate("/dashboard", { replace: true });
    } catch {
      setSelectedTenantId(previous);
      setError("Workspace could not be changed. Your previous workspace is still selected.");
      revalidate();
    } finally { setBusy(false); }
  }
  if (tenants.length < 2) return null;
  return <div className="workspace-switcher">
    <label>Workspace <select aria-label="Workspace" disabled={busy} value={user?.tenant_id || ""} onChange={(event) => change(event.target.value)}>
      {tenants.map((tenant) => <option key={tenant.tenant_id} value={tenant.tenant_id}>{tenant.name || `Workspace ${tenant.tenant_id}`}</option>)}
    </select></label>
    {error && <p role="alert">{error}</p>}
  </div>;
}
