import { useCallback, useEffect, useMemo, useState } from "react";
import matrix from "./planMatrix.generated.json";
import { Link, useLocation } from "react-router-dom";
import { apiFetch, getApiUrl, readApiResponse } from "../utils/apiClient";

import { DENIED, WorkspaceContext, useWorkspaceCapabilities, workspaceRouteCapabilities } from "./capabilityContext";

export function WorkspaceCapabilitiesProvider({ user, children }) {
  const { pathname } = useLocation();
  const identity = `${user?.tenant_id || ""}:${user?.id || ""}:${pathname}`;
  const [snapshot, setSnapshot] = useState(null);
  const [refresh, setRefresh] = useState(0);
  const revalidate = useCallback(() => { setSnapshot(null); setRefresh((value) => value + 1); }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timer;
    async function load() {
      try {
        const response = await apiFetch(getApiUrl("/billing/entitlements"), { cache: "no-store", signal: controller.signal });
        const body = await readApiResponse(response);
        const state = body?.entitlements;
        if (!response.ok || !state || Number(state.tenant_id) !== Number(user?.tenant_id) || !Array.isArray(state.capabilities)) throw new Error("Commercial access unavailable");
        if (controller.signal.aborted) return;
        setSnapshot({ identity, state });
        const next = Date.parse(state.next_transition_at || "");
        if (Number.isFinite(next)) timer = setTimeout(revalidate, Math.max(1, Math.min(next - Date.now() + 50, 2147483647)));
      } catch {
        if (!controller.signal.aborted) setSnapshot({ identity, error: true });
      }
    }
    load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [identity, user?.tenant_id, revalidate, refresh]);

  useEffect(() => {
    window.addEventListener("focus", revalidate);
    window.addEventListener("madar:commercial-denied", revalidate);
    return () => {
      window.removeEventListener("focus", revalidate);
      window.removeEventListener("madar:commercial-denied", revalidate);
    };
  }, [revalidate]);

  const value = useMemo(() => {
    if (snapshot?.identity !== identity || !snapshot?.state) return { ...DENIED, error: snapshot?.identity === identity && snapshot?.error, revalidate };
    const capabilities = (snapshot.state.operational_capabilities || snapshot.state.capabilities).filter((capability) => matrix.capabilities.includes(capability));
    return { ready: true, capabilities, state: snapshot.state, revision: snapshot.state.entitlement_revision || `${identity}:operator`, can: (capability) => capabilities.includes(capability), revalidate };
  }, [identity, snapshot, revalidate]);
  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function WorkspaceRouteAccess({ children }) {
  const { pathname } = useLocation();
  const { ready, error, can, revalidate } = useWorkspaceCapabilities();
  const required = workspaceRouteCapabilities(pathname);
  // Billing and security remain reachable while commercial access is unresolved.
  if (!required.length) return children;
  if (!ready) return <section role="status"><p>{error ? "Workspace access could not be verified." : "Checking workspace access…"}</p>{error && <button onClick={revalidate}>Try again</button>}</section>;
  if (!required.some(can)) return <section role="status"><h1>Plan access required</h1><p>This workspace’s plan does not include this feature.</p><Link to="/my-plan">View commercial access</Link></section>;
  return children;
}
