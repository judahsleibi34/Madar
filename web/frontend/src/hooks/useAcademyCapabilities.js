import { useEffect, useState } from "react";
import { apiFetch, getApiUrl } from "../utils/apiClient";

export default function useAcademyCapabilities(user, enabled = true) {
  const [state, setState] = useState(null);
  const identity = `${user?.tenant_id || ""}:${user?.id || ""}`;
  useEffect(() => {
    if (!enabled || !user?.id) return;
    let active = true;
    apiFetch(getApiUrl("/elearning/programmes/capabilities"), { cache: "no-store" })
      .then(response => response.ok ? response.json() : null)
      .then(value => { if (active) setState({ identity, value }); })
      .catch(() => { if (active) setState({ identity, value: null }); });
    return () => { active = false; };
  }, [identity, enabled, user?.id]);
  return !enabled || !user?.id ? null : state?.identity === identity ? state.value : undefined;
}
