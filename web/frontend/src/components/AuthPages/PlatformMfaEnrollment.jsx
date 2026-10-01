import { useState } from "react";
import { postAuthJson, readApiError } from "../../utils/apiClient";

// Only the encrypted pending-login cookie is accepted by these endpoints.
export default function PlatformMfaEnrollment({ onLoginSuccess, onCancel }) {
  const [enrollment, setEnrollment] = useState(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const enroll = async () => {
    setBusy(true); setError("");
    try {
      const { response, data } = await postAuthJson("/auth/mfa/login/enroll", {});
      if (!response.ok) throw new Error(readApiError(data));
      setEnrollment(data);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  const verify = async event => {
    event.preventDefault(); event.stopPropagation(); setBusy(true); setError("");
    try {
      const { response, data } = await postAuthJson("/auth/mfa/login/enroll/verify", { factor_id: enrollment.factor.id, code });
      if (!response.ok) throw new Error(readApiError(data));
      setCode(""); await onLoginSuccess(data.user);
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  const qr = enrollment?.totp?.qr_code || "";
  const qrSrc = qr.startsWith("data:image/") ? qr : qr.startsWith("<svg") ? `data:image/svg+xml;charset=utf-8,${encodeURIComponent(qr)}` : "";
  return <main className="auth-page"><section className="auth-form"><h1>Administrator MFA enrollment required</h1>
    <p>Set up an authenticator before entering Platform Administration. If this session expires, sign in again.</p>
    {!enrollment ? <button type="button" disabled={busy} onClick={enroll}>Set up authenticator</button> : <form onSubmit={verify}>
      {qrSrc && <img src={qrSrc} alt="Scan with your authenticator" />}
      <label>Authenticator setup URI<input readOnly value={enrollment.totp?.uri || ""} /></label>
      <label>Verification code<input autoFocus required inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" value={code} onChange={event => setCode(event.target.value)} /></label>
      <button disabled={busy}>{busy ? "Verifying…" : "Verify account"}</button>
    </form>}
    {error && <p role="alert">{error}</p>}
    <button type="button" disabled={busy} onClick={async () => { if (await onCancel() === false) setError("Could not cancel MFA login. Try again."); }}>Return to sign in</button>
  </section></main>;
}
