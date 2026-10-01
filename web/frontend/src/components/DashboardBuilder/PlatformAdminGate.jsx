import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { apiFetch, getApiUrl, readApiError, registerAdminStepUpHandler } from "../../utils/apiClient";
import AdminCommercialStepUp from "./AdminCommercialStepUp";

export default function PlatformAdminGate({ user, children, onLogout }) {
  const [state, setState] = useState("loading");
  const [error, setError] = useState("");
  const [admitted, setAdmitted] = useState(false);
  const focusBeforeChallenge = useRef(null);
  const contentRef = useRef(null);
  const pending = useRef(null);
  const inFlight = useRef(null);
  const active = useRef(true);
  const challenge = useCallback(() => {
    setState("challenge");
    if (!pending.current) {
      focusBeforeChallenge.current = document.activeElement;
      let resolve;
      const promise = new Promise(done => { resolve = done; });
      pending.current = { promise, resolve };
    }
    return pending.current.promise;
  }, []);
  const check = useCallback(() => {
    if (inFlight.current) return inFlight.current;
    inFlight.current = (async () => {
      try {
        const response = await apiFetch(getApiUrl("/auth/mfa/status"), { cache: "no-store" });
        const data = await response.json();
        if (!response.ok) throw new Error(readApiError(data));
        if (!active.current) return false;
        setError("");
        if (data.aal?.current_level !== "aal2") { challenge(); return false; }
        setAdmitted(true);
        setState("ready");
        pending.current?.resolve(true);
        pending.current = null;
        return true;
      } catch (err) {
        if (active.current) { setError(err.message); setState("error"); }
        return false;
      } finally { inFlight.current = null; }
    })();
    return inFlight.current;
  }, [challenge]);
  const location = useLocation();
  useEffect(() => {
    active.current = true;
    const unregister = registerAdminStepUpHandler(challenge);
    return () => {
      active.current = false;
      unregister();
      pending.current?.resolve(false);
      pending.current = null;
    };
  }, [challenge]);
  useEffect(() => {
    const timer = setTimeout(check, 0);
    const onFocus = () => { if (document.visibilityState !== "hidden") check(); };
    window.addEventListener("focus", onFocus);
    return () => { clearTimeout(timer); window.removeEventListener("focus", onFocus); };
  }, [check, location.pathname]);
  useEffect(() => {
    if (state !== "ready") return;
    const previous = focusBeforeChallenge.current;
    if (previous?.isConnected && previous.closest("[hidden]") === null) previous.focus();
    else {
      const heading = contentRef.current?.querySelector("h1");
      if (heading) { heading.tabIndex = -1; heading.focus(); }
    }
    focusBeforeChallenge.current = null;
  }, [state]);
  return <>
    {state !== "ready" && <main className="dashboard-page" aria-busy={state === "loading"}>
      {state === "loading" ? <p role="status">Checking administrator assurance…</p> : <>
        <AdminCommercialStepUp userId={user.id} onVerified={check} />
        {error && <p role="alert">{error}</p>}
        <button type="button" onClick={check}>Check MFA status</button>
      </>}
      <button type="button" onClick={onLogout}>Sign out</button>
    </main>}
    {admitted && <div ref={contentRef} hidden={state !== "ready"}>{children}</div>}
  </>;
}
