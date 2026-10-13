import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { BadgeCheck, CheckCircle2, ShieldCheck, XCircle } from "lucide-react";
import { apiFetch, getApiUrl } from "../../utils/apiClient";
import { OwnerHeader, OwnerPage, OwnerState, OwnerTable, OwnerPagination } from "./OwnerUI";
import "../../styles/academy-admin-controls.css";

async function send(path, method, body) {
  const response = await apiFetch(getApiUrl(`/elearning/owner${path}`), { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!response.ok) { const failure = new Error("request_failed"); failure.status = response.status; throw failure; }
  return response.json();
}

/** Approve or reject a pending referral reward (rejection needs a reason). */
export function RewardReviewControl({ referralId, onDone }) {
  const { t } = useTranslation("dashboard");
  const [reject, setReject] = useState(false), [note, setNote] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState(false);
  async function decide(decision) {
    setBusy(true); setError(false);
    try { await send(`/rewards/${encodeURIComponent(referralId)}/review`, "POST", { decision, note: note.trim() }); onDone?.(); }
    catch { setError(true); } finally { setBusy(false); }
  }
  return <div className="admin-control">
    {!reject ? <div className="admin-control-actions">
      <button type="button" className="ecommerce-primary-button" disabled={busy} onClick={() => decide("earned")}><CheckCircle2 size={16} aria-hidden="true" />{t("elearning.adminControls.approveReward")}</button>
      <button type="button" className="ecommerce-secondary-button" disabled={busy} onClick={() => setReject(true)}><XCircle size={16} aria-hidden="true" />{t("elearning.adminControls.rejectReward")}</button>
    </div> : <form className="admin-control-form" onSubmit={event => { event.preventDefault(); decide("rejected"); }}>
      <label>{t("elearning.adminControls.reason")}<textarea required maxLength={1000} value={note} onChange={event => setNote(event.target.value)} /></label>
      <div className="admin-control-actions"><button className="ecommerce-primary-button" disabled={busy || !note.trim()}>{t("elearning.adminControls.confirmReject")}</button><button type="button" className="ecommerce-secondary-button" onClick={() => setReject(false)}>{t("elearning.commerce.cancel")}</button></div>
    </form>}
    {error && <p role="alert">{t("elearning.adminControls.error")}</p>}
  </div>;
}

/** Manual "Verified PAU Student" and the audited Tuition Support override for one learner. */
export function MemberControls({ learner, institutionLabel, onDone }) {
  const { t } = useTranslation("dashboard");
  const [note, setNote] = useState(""), [mode, setMode] = useState(learner.tuition_override == null ? "automatic" : learner.tuition_override ? "eligible" : "not_eligible");
  const [reason, setReason] = useState(""), [busy, setBusy] = useState(false), [status, setStatus] = useState("");
  async function run(action) {
    setBusy(true); setStatus("");
    try { await action(); setStatus("saved"); onDone?.(); } catch { setStatus("error"); } finally { setBusy(false); }
  }
  const verified = learner.institution_manually_verified === true;
  return <div className="admin-control admin-member-controls">
    {learner.institution_verified && <form className="admin-control-form" onSubmit={event => { event.preventDefault(); run(() => send(`/members/${learner.user_id}/institution-verification`, "PUT", { verified: !verified, note: note.trim() })); }}>
      <h4><BadgeCheck size={16} aria-hidden="true" />{t("elearning.adminControls.verifiedTitle", { label: institutionLabel })}</h4>
      <label>{t("elearning.adminControls.note")}<input maxLength={1000} value={note} onChange={event => setNote(event.target.value)} /></label>
      <button className={verified ? "ecommerce-secondary-button" : "ecommerce-primary-button"} disabled={busy}>{t(verified ? "elearning.adminControls.removeVerification" : "elearning.adminControls.markVerified", { label: institutionLabel })}</button>
    </form>}
    <form className="admin-control-form" onSubmit={event => { event.preventDefault(); run(() => send(`/members/${learner.user_id}/tuition-override`, "PUT", { eligible: mode === "automatic" ? null : mode === "eligible", reason: reason.trim() })); }}>
      <h4><ShieldCheck size={16} aria-hidden="true" />{t("elearning.adminControls.overrideTitle")}</h4>
      <label>{t("elearning.adminControls.overrideMode")}<select value={mode} onChange={event => setMode(event.target.value)}>{["automatic", "eligible", "not_eligible"].map(value => <option key={value} value={value}>{t(`elearning.adminControls.override_${value}`)}</option>)}</select></label>
      <label>{t("elearning.adminControls.reasonRequired")}<textarea required maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} /></label>
      <button className="ecommerce-primary-button" disabled={busy || !reason.trim()}>{t("elearning.adminControls.saveOverride")}</button>
    </form>
    <p role="status">{status ? t(`elearning.adminControls.${status}`) : ""}</p>
  </div>;
}

/** EH / Audit log: who changed what, newest first (read-only). */
export function AcademyAuditLogPage() {
  const { t, i18n } = useTranslation("dashboard");
  const [data, setData] = useState(null), [error, setError] = useState(false), [page, setPage] = useState(0), [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    apiFetch(getApiUrl(`/elearning/owner/audit-log?limit=50&offset=${page * 50}`)).then(response => { if (!response.ok) throw new Error(); return response.json(); })
      .then(value => { if (active) { setData(value); setError(false); } }).catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [page, attempt]);
  const entries = (data?.entries || []).slice(0, 50);
  const details = metadata => Object.entries(metadata || {}).filter(([, value]) => value !== null && value !== "").map(([key, value]) => `${key}: ${typeof value === "object" ? JSON.stringify(value) : value}`).join(" · ");
  return <OwnerPage><OwnerHeader title={t("elearning.adminControls.auditTitle")} description={t("elearning.adminControls.auditHelp")} />
    <OwnerState error={error} retry={() => { setError(false); setAttempt(value => value + 1); }} loading={!data && !error} empty={data && !entries.length && t("elearning.adminControls.auditEmpty")} />
    {entries.length > 0 && <OwnerTable caption={t("elearning.adminControls.auditTitle")} columns={[t("elearning.adminControls.when"), t("elearning.adminControls.who"), t("elearning.adminControls.action"), t("elearning.adminControls.details")]}>
      {entries.map(row => <tr key={row.id}>
        <td>{new Date(row.created_at).toLocaleString(i18n.language)}</td>
        <td>{row.actor_name || row.actor_email || t("elearning.ui.member")}</td>
        <td dir="ltr"><code>{row.action}</code>{row.target_id && <small> · {row.target_type} {row.target_id}</small>}</td>
        <td dir="auto">{details(row.metadata)}</td>
      </tr>)}
    </OwnerTable>}
    {data && <OwnerPagination page={page} setPage={setPage} more={Boolean(data.has_more)} />}
  </OwnerPage>;
}
