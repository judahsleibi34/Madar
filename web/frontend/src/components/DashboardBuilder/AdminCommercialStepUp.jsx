import { useEffect, useState } from "react";
import { apiFetch, getApiUrl, readApiError } from "../../utils/apiClient";
import SecurityMfaPage from "./SecurityMfaPage";

// Uses the existing authenticated challenge + verify endpoint, which sets the
// upgraded HttpOnly session cookies. The server still checks AAL on every action.
export default function AdminCommercialStepUp({ userId, onVerified }) {
  const [factors, setFactors] = useState([]);
  const [factor, setFactor] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    apiFetch(getApiUrl("/auth/mfa/status"), { cache: "no-store" }).then(async response => {
      const data = await response.json();
      if (!response.ok) throw new Error(readApiError(data));
      if (active) { const verified = (data.factors || []).filter(item => item.status === "verified"); setFactors(verified); setFactor(verified[0]?.id || ""); }
    }).catch(err => { if (active) setError(err.message); });
    return () => { active = false; };
  }, []);
  const verify = async event => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const response = await apiFetch(getApiUrl("/auth/mfa/enroll/verify"), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ factor_id: factor, code }) });
      const data = await response.json();
      if (!response.ok) throw new Error(readApiError(data));
      setCode(""); await onVerified();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  return <section><h2>MFA verification required</h2><p>Verify your account, then review your commercial action again. No mutation is automatically retried.</p>
    {factors.length ? <form onSubmit={verify}><label>Authenticator<select value={factor} onChange={event => setFactor(event.target.value)}>{factors.map(item => <option key={item.id} value={item.id}>{item.friendly_name || "Authenticator"}</option>)}</select></label><label>Verification code<input required inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" value={code} onChange={event => setCode(event.target.value)} /></label><button disabled={busy}>{busy ? "Verifying…" : "Verify account"}</button></form> : <SecurityMfaPage embedded cacheKey={userId} />}
    {error && <p role="alert">{error}</p>}
  </section>;
}
