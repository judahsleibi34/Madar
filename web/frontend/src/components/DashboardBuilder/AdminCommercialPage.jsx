import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { commercialRequest, moduleNames, money, date } from "../../services/adminCommercialApi";
import AdminCommercialStepUp from "./AdminCommercialStepUp";
import "../../styles/admin/commercial.css";

const names = {
  modules: "Manage modules", suspend: "Suspend commercial access", reactivate: "Reactivate commercial access",
  "manual-payments": "Record manual payment", "complimentary-access": "Grant complimentary access",
  "revoke-access": "Revoke access", "correct-payment": "Correct payment evidence", "review-inactive": "Review as inactive",
};
const effects = {
  modules: "Assignment does not record payment or grant dated access. Removing a module ends that module’s automatic founding price lock.",
  suspend: "New paid SaaS use will be restricted. Login and identity remain intact. Historical records are retained.",
  reactivate: "Removes the administrative hold only. Does not record payment, extend expired access, restore cancelled modules, or restore forfeited price locks.",
  "manual-payments": "Records payment evidence and dated coverage. Does not clear a commercial hold. Prepared pricing is not eligible for first payment until sales activation.",
  "complimentary-access": "Dated complimentary access, not a zero-dollar payment. Does not create founding paid rights or clear a hold.",
  "revoke-access": "Ends the selected access period. This is distinct from a reversible commercial hold. Historical evidence remains stored.",
  "correct-payment": "Appends correction evidence; the original payment remains visible. Coverage is not silently extended.",
  "review-inactive": "Explicitly resolves legacy review as inactive; does not grant modules or access.",
};

function Pricing({ pricing }) {
  return <><strong>{money(pricing?.recurring_minor, pricing?.currency)} / {pricing?.billing_interval || "interval unavailable"}</strong>
    {(pricing?.price_groups || []).map(group => <p key={group.price_book_id}>{group.module_ids.map(id => moduleNames[id] || id).join(" + ")} · {group.price_book_id} · {money(group.recurring_minor, pricing.currency)} · {group.grandfathered ? "Continuous paid basis protected" : "No continuous paid lock"} · {group.new_sales_active ? "Open for new sales" : "Not open for new sales"}</p>)}</>;
}

function CommercialDialog({ action, snapshot, history, tenantId, onClose, onSuccess, onConflict, onStepUp }) {
  const dialog = useRef(null);
  const inFlight = useRef(false);
  const intent = useRef(null);
  const draftRevision = useRef(0);
  const ent = snapshot.entitlements || {};
  const assigned = ent.assigned_modules || [];
  const [fields, setFields] = useState({ module_ids: assigned, reason: "", reference: "", billing_months: 1, method: "bank_transfer", actual_minor: "", paid_at: "", valid_from: "", valid_until: "", receipt_reference: "", override_reason: "", period_id: "", payment_id: "", supersedes_period_id: "" });
  const [quote, setQuote] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [stale, setStale] = useState(false);
  const [needsMfa, setNeedsMfa] = useState(false);
  const requiresQuote = action === "modules" || action === "manual-payments";
  const grant = ["manual-payments", "complimentary-access"].includes(action);
  const payment = ["manual-payments", "correct-payment"].includes(action);
  useEffect(() => {
    const node = dialog.current;
    node.showModal?.();
    return () => node.close?.();
  }, []);
  const change = (key, value) => {
    if (intent.current) { setError("This request may already have reached the server. Retry the identical request or close and inspect history before starting a different intent."); return; }
    draftRevision.current++;
    setFields(previous => ({ ...previous, [key]: value }));
    setConfirmed(false); setQuote(null);
  };
  const preview = async () => {
    const requestedDraft = draftRevision.current;
    setQuote(null); setConfirmed(false);
    setBusy(true); setError("");
    try {
      const result = await commercialRequest(`tenants/${tenantId}/modules/quote`, { module_ids: fields.module_ids, billing_months: Number(fields.billing_months) });
      if (requestedDraft !== draftRevision.current) return;
      if (result.quote.revision !== snapshot.commercial_access.revision) { setStale(true); await onConflict(); throw new Error("Commercial state changed. Close and review the refreshed state."); }
      setQuote(result.quote);
    } catch (err) { setError(err.message); if (err.code === "aal2_required") { setNeedsMfa(true); setConfirmed(false); onStepUp(); } }
    finally { setBusy(false); }
  };
  const submit = async (event) => {
    event.preventDefault();
    if (inFlight.current || needsMfa || stale || !confirmed || (requiresQuote && !quote) || (action === "manual-payments" && !quote?.payment_eligible)) return;
    const body = { expected_revision: snapshot.commercial_access.revision, reason: fields.reason.trim(), ...(fields.reference ? { reference: fields.reference } : {}) };
    if (body.reason.length < 3) { setError("Enter a reason of at least three characters."); return; }
    if (action === "modules" || grant) body.module_ids = fields.module_ids;
    if (action === "modules") body.price_books = Object.fromEntries(Object.entries(quote.module_basis || {}).map(([id, basis]) => [id, basis.price_book_id]));
    if (grant) {
      if (!fields.module_ids.length) { setError("Select at least one assigned module."); return; }
      body.valid_from = new Date(fields.valid_from).toISOString(); body.valid_until = new Date(fields.valid_until).toISOString();
      if (fields.supersedes_period_id) body.supersedes_period_id = fields.supersedes_period_id;
    }
    if (payment) {
      body.actual_minor = Number(fields.actual_minor); body.paid_at = new Date(fields.paid_at).toISOString(); body.receipt_reference = fields.receipt_reference;
      if (fields.override_reason) body.override_reason = fields.override_reason;
    }
    if (action === "manual-payments") { body.method = fields.method; body.billing_months = Number(fields.billing_months); body.currency = "USD"; }
    if (action === "revoke-access") body.period_id = fields.period_id;
    if (action === "correct-payment") body.payment_id = fields.payment_id;
    if (!intent.current) intent.current = { ...body, idempotency_key: crypto.randomUUID() };
    inFlight.current = true; setBusy(true); setError("");
    try {
      await commercialRequest(`tenants/${tenantId}/${action}`, intent.current);
      await onSuccess();
    } catch (err) {
      setError(err.message);
      if (err.code === "aal2_required") { setNeedsMfa(true); setConfirmed(false); onStepUp(); }
      if (err.status === 409) { setStale(true); await onConflict(); setError(`${err.message} State refreshed. Close and review again before a new action.`); }
    } finally { inFlight.current = false; setBusy(false); }
  };
  const input = (key, label, type = "text", required = true) => <label>{label}<input type={type} required={required} value={fields[key]} onChange={e => change(key, e.target.value)} {...(type === "number" ? { min: 1, step: 1 } : {})} /></label>;
  const removed = assigned.filter(id => !fields.module_ids.includes(id));
  return <dialog ref={dialog} open={!HTMLDialogElement.prototype.showModal} className="commercial-dialog" aria-labelledby="commercial-action-title" onCancel={e => { if (busy) e.preventDefault(); else onClose(); }}>
    <form onSubmit={submit}>
      <h2 id="commercial-action-title">{names[action]}</h2>
      <p>{snapshot.tenant?.brand_name || `Tenant ${tenantId}`} · {snapshot.commercial_access.access_state} · Revision {snapshot.commercial_access.revision}</p>
      <p>{effects[action]}</p>
      <p>Existing modules: {assigned.map(id => moduleNames[id]).join(", ") || "None / legacy review required"}</p>
      {action === "modules" && <><h3>Current pricing</h3><Pricing pricing={ent.pricing} /></>}
      {(action === "modules" || grant) && <fieldset><legend>{action === "modules" ? "Proposed modules (none means full cancellation)" : "Assigned modules covered"}</legend>{Object.entries(moduleNames).map(([id, label]) => <label key={id}><input type="checkbox" checked={fields.module_ids.includes(id)} disabled={grant} onChange={e => change("module_ids", e.target.checked ? [...fields.module_ids, id] : fields.module_ids.filter(m => m !== id))} />{label}</label>)}</fieldset>}
      {action === "modules" && removed.length > 0 && <p className="commercial-warning" role="status">Price-lock warning: removal of {removed.map(id => moduleNames[id]).join(", ")} forfeits its continuous founding basis. Re-adding does not automatically restore launch eligibility.</p>}
      {grant && <>{input("valid_from", "Coverage starts (local time)", "datetime-local")}{input("valid_until", "Coverage ends (local time)", "datetime-local")}<label>Explicitly supersede an access period<select value={fields.supersedes_period_id} onChange={e => change("supersedes_period_id", e.target.value)}><option value="">Do not supersede (overlaps will be rejected)</option>{(history.periods || []).filter(p => !p.revoked_at).map(p => <option key={p.id} value={p.id}>{p.id} · {date(p.valid_until)}</option>)}</select></label></>}
      {action === "manual-payments" && <>{input("billing_months", "Billing months (coverage must match calendar months)", "number")}<label>Method<select value={fields.method} onChange={e => change("method", e.target.value)}>{["bank_transfer", "cash", "other_manual"].map(method => <option key={method}>{method}</option>)}</select></label></>}
      {payment && <>{input("actual_minor", "Received amount (USD minor units; 100 = $1)", "number")}{input("paid_at", "Payment received at (local time)", "datetime-local")}{input("receipt_reference", "Safe receipt/reference")}{input("override_reason", "Amount override reason (only if received amount differs)", "text", false)}</>}
      {action === "revoke-access" && <label>Access period<select required value={fields.period_id} onChange={e => change("period_id", e.target.value)}><option value="">Select period</option>{(history.periods || []).filter(p => !p.revoked_at).map(p => <option key={p.id} value={p.id}>{p.id} · {p.source_type} · {date(p.valid_from)} — {date(p.valid_until)}</option>)}</select></label>}
      {action === "correct-payment" && <label>Original payment<select required value={fields.payment_id} onChange={e => change("payment_id", e.target.value)}><option value="">Select payment</option>{(history.payments || []).map(p => <option key={p.id} value={p.id}>{p.id} · {money(p.actual_minor, p.currency)} · {p.receipt_reference}</option>)}</select></label>}
      <label>Required reason<textarea required minLength={3} maxLength={1000} value={fields.reason} onChange={e => change("reason", e.target.value)} /></label>
      {input("reference", "Safe action reference (optional)", "text", false)}
      {requiresQuote && <><button type="button" disabled={busy || stale || !!intent.current} onClick={preview}>Preview server quote</button>{quote && <section aria-label="Server quote"><Pricing pricing={quote.pricing} />{action === "manual-payments" && <p>Expected payment: {money(quote.expected_payment_minor, quote.pricing.currency)}</p>}{action === "manual-payments" && !quote.payment_eligible && <p role="alert">This basis is not eligible for payment. Launch pricing is prepared, not activated; use an approved complimentary workflow if appropriate.</p>}<p>Proposed modules: {quote.pricing.module_ids.map(id => moduleNames[id]).join(", ") || "Full cancellation"}</p></section>}</>}
      <label><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} required />I have reviewed this tenant, commercial basis and the effect of this action.</label>
      {error && <p role="alert">{error}</p>}
      <div className="commercial-actions"><button type="button" disabled={busy} onClick={onClose}>Cancel</button><button type="submit" disabled={busy || needsMfa || stale || !confirmed || fields.reason.trim().length < 3 || (requiresQuote && !quote) || (action === "manual-payments" && !quote?.payment_eligible)}>{busy ? "Submitting…" : "Confirm action"}</button></div>
    </form>
    {needsMfa && <AdminCommercialStepUp onVerified={async () => { setNeedsMfa(false); setError("Account verified. Review and confirm the unchanged action again."); setConfirmed(false); }} />}
  </dialog>;
}

export default function AdminCommercialPage({ currentUser }) {
  const { tenantId } = useParams();
  const [loadedSnapshot, setSnapshot] = useState(null);
  const snapshot = loadedSnapshot?._inspectedTenantId === tenantId ? loadedSnapshot : null;
  const loadSequence = useRef(0);
  const invalidateLoads = useCallback(() => { loadSequence.current++; }, []);
  const [history, setHistory] = useState({});
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [stepUp, setStepUp] = useState(false);
  const [action, setAction] = useState("");
  const [success, setSuccess] = useState("");
  const load = useCallback(async () => {
    if (currentUser?.user_type !== "admin") { setLoading(false); return false; }
    const sequence = ++loadSequence.current;
    setLoading(true); setError("");
    try {
      const [state, records, catalog] = await Promise.all([commercialRequest(`tenants/${tenantId}/modules`), commercialRequest(`tenants/${tenantId}/access-history`), commercialRequest("price-books")]);
      if (sequence !== loadSequence.current) return false;
      setSnapshot({ ...state, _inspectedTenantId: tenantId }); setHistory(records); setBooks(catalog.price_books || []); setStepUp(false);
      return true;
    } catch (err) { if (sequence === loadSequence.current) { setError(err.message); if (err.code === "aal2_required") setStepUp(true); } return false; }
    finally { if (sequence === loadSequence.current) setLoading(false); }
  }, [tenantId, currentUser?.user_type]);
  useEffect(() => { let active = true; queueMicrotask(() => { if (active) load(); }); return () => { active = false; invalidateLoads(); }; }, [load, invalidateLoads]);
  if (currentUser?.user_type !== "admin") return <section><h1>Platform administrator access required</h1></section>;
  const ent = snapshot?.entitlements || {};
  const state = snapshot?.commercial_access || {};
  const period = state.period;
  return <main className="commercial-page dashboard-page">
    <header className="app-page-intro"><Link to="/admin/users">← User & tenant management</Link><h1>Commercial access</h1><p>{snapshot?.tenant?.brand_name || `Tenant ${tenantId}`} · Tenant ID {tenantId} · Owner: {snapshot?.tenant?.owner_name || "Unavailable"}</p></header>
    {error && <p role="alert">{error}</p>}{success && <p role="status">{success}</p>}
    {stepUp && <section className="commercial-card"><AdminCommercialStepUp userId={currentUser?.id} onVerified={load} /></section>}
    <button type="button" disabled={loading} onClick={load}>Reload authoritative state</button>
    {loading && <p role="status">Loading commercial state…</p>}
    {snapshot && !loading && <>
      <div className="commercial-grid">
        <section className="commercial-card"><h2>Commercial status</h2><dl><dt>Effective state</dt><dd>{state.access_state || "Unavailable"}</dd><dt>Review</dt><dd>{state.review_state || "Unavailable"}</dd><dt>Revision</dt><dd>{state.revision ?? "Unavailable"}</dd><dt>Next transition</dt><dd>{date(state.next_transition_at)}</dd><dt>Commercial hold</dt><dd>{snapshot.hold?.commercial_suspended_at ? `Held since ${date(snapshot.hold.commercial_suspended_at)}` : "No administrative hold"}</dd><dt>Hold reason</dt><dd>{snapshot.hold?.commercial_suspension_reason || "None"}</dd><dt>Tenant lifecycle</dt><dd>Unavailable in current tenant API</dd></dl></section>
        <section className="commercial-card"><h2>Current recurring core amount</h2><Pricing pricing={ent.pricing} /><p>Add-ons and variable provider costs are separate.</p></section>
        <section className="commercial-card"><h2>Dated access</h2>{period ? <><p>{period.source_type || "Source unavailable"}</p><p>{date(period.valid_from)} — {date(period.valid_until)}</p><p>{(period.module_ids || []).map(id => moduleNames[id]).join(", ") || "Historical legacy coverage"}</p></> : <p>No current access period</p>}</section>
      </div>
      <section className="commercial-card"><h2>Assigned modules & founding basis</h2><div className="commercial-grid">{Object.entries(moduleNames).map(([id, label]) => { const basis = ent.module_commercial_basis?.[id]; return <article key={id}><h3>{label}</h3><p>{(ent.assigned_modules || []).includes(id) ? "Assigned" : "Not assigned"} · {Array.isArray(ent.effective_modules) ? ent.effective_modules.includes(id) ? "Effective" : "Not effective" : ent.commercial_denial_code ? "Not effective" : "Effective module state unavailable"}</p>{basis && <><p>{basis.price_book_id} · {basis.paid_since ? (basis.price_book_id === "launch_2026" ? "Founding price protected while continuously assigned" : "Continuous paid price-book basis") : "No founding paid lock"}</p><p>Acquired: {date(basis.acquired_at)} · Paid since: {date(basis.paid_since)}</p></>}</article>; })}</div></section>
      {ent.legacy_assignment_requires_review && <section className="commercial-warning"><h2>Legacy commercial state — Review required</h2><p>Historical legacy plan: {ent.assigned_plan_id || "Unavailable"}. This is historical context only. Explicit reviewed modules and legitimate dated coverage are required; no automatic Business/Business Plus mapping.</p></section>}
      <section className="commercial-card"><h2>Commercial actions</h2><div className="commercial-actions">{Object.entries(names).filter(([id]) => id !== "suspend" || !snapshot.hold?.commercial_suspended_at).filter(([id]) => id !== "reactivate" || snapshot.hold?.commercial_suspended_at).map(([id, label]) => <button key={id} disabled={!!error} onClick={() => { setSuccess(""); setAction(id); }}>{label}</button>)}</div></section>
      <section className="commercial-card"><h2>Effective capabilities</h2><p>Source: {ent.source || "Unavailable"} · {ent.commercial_denial_code || ent.reason || "No denial reported"}</p><ul>{(ent.capabilities || []).map(capability => <li key={capability}>{capability}</li>)}</ul><h3>Current add-ons</h3>{(state.addons || []).length ? state.addons.map(addon => <p key={addon.id}>{addon.addon_id} · Quantity {addon.quantity ?? "Unavailable"} · {addon.state}</p>) : <p>No current valid add-ons</p>}<p>Storage allowance: {ent.allowances?.storage_bytes != null ? `${ent.allowances.storage_bytes} bytes` : "Unavailable"}</p></section>
      <section className="commercial-card"><h2>Payments</h2><HistoryTable rows={history.payments} columns={[["Received", p => money(p.actual_minor, p.currency)], ["Date", p => date(p.paid_at)], ["Method", p => p.method], ["Reference", p => p.receipt_reference], ["Correction of", p => p.corrects_payment_id], ["Modules / price snapshot", p => snapshotText(p)]]} /></section>
      <section className="commercial-card"><h2>Access periods</h2><HistoryTable rows={history.periods} columns={[["Source", p => p.source_type], ["From", p => date(p.valid_from)], ["Until", p => date(p.valid_until)], ["Revoked", p => p.revoked_at ? date(p.revoked_at) : "No"], ["Modules / price snapshot", snapshotText]]} /></section>
      <section className="commercial-card"><h2>Commercial events / audit context</h2><p>Latest 100 records per history section. Immutable ledger evidence is retained.</p><HistoryTable rows={history.events} columns={[["Action", p => p.operation], ["Actor", p => p.actor_user_id], ["Time", p => date(p.created_at)], ["Revision", p => `${p.result?.previous_state?.revision ?? "Unavailable"} → ${p.result?.revision ?? "Unavailable"}`], ["Reason", p => p.request_payload?.request?.reason || p.result?.reason], ["Reference", p => p.result?.reference], ["AAL / request", p => `${p.aal || "Unavailable"} · ${p.request_id || "Unavailable"}`], ["State transition", p => `${p.result?.previous_state?.access_state || "Unavailable"} → ${p.result?.resulting_state?.access_state || "Unavailable"}`], ["Pricing", p => snapshotText({ module_ids: p.result?.price_snapshot?.module_ids, price_snapshot: p.result?.price_snapshot })]]} /></section>
      <section className="commercial-card"><h2>Price books (read-only)</h2>{books.length ? books.map(book => <article key={book.id}><h3>{book.id} · Version {book.version}</h3><p>{book.currency} / {book.billing_interval} · Effective {date(book.effective_from)}</p><p>Sales start: {date(book.sales_start_at)} · Sales end: {book.sales_end_at ? date(book.sales_end_at) : "No closing date configured"}</p><p>{!book.sales_start_at ? "Prepared — not activated" : book.new_sales_active ? "Open for new sales" : "Closed to new sales"} · Continuous paid grandfathered renewals remain eligible under the canonical contract.</p><ul>{Object.entries(book.standalone_minor || {}).map(([id, amount]) => <li key={id}>{moduleNames[id] || id}: {money(amount, book.currency)}</li>)}{Object.entries(book.bundle_minor || {}).map(([count, amount]) => <li key={count}>{count} modules: {money(amount, book.currency)}</li>)}</ul></article>) : <p>No price books available</p>}</section>
    </>}
    {action && snapshot && <CommercialDialog key={`${tenantId}-${action}`} action={action} snapshot={snapshot} history={history} tenantId={tenantId} onClose={() => setAction("")} onStepUp={() => setStepUp(true)} onConflict={load} onSuccess={async () => { setAction(""); setSuccess("Commercial action recorded. Reloading authoritative state."); await load(); }} />}
  </main>;
}
function snapshotText(row) { return `${(row.module_ids || []).map(id => moduleNames[id] || id).join(", ") || `Legacy ${row.plan_id || "basis unavailable"}`} · ${money(row.price_snapshot?.recurring_minor, row.price_snapshot?.currency)} · ${(row.price_snapshot?.price_groups || []).map(group => group.price_book_id).join(", ") || "Historical pricing unavailable"}`; }
function HistoryTable({ rows = [], columns }) {
  if (!rows.length) return <p>No records</p>;
  return <div className="commercial-table-wrap"><table><thead><tr>{columns.map(([label]) => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{rows.map(row => <tr key={row.id}>{columns.map(([label, read]) => <td key={label}>{read(row) ?? "Unavailable"}</td>)}</tr>)}</tbody></table></div>;
}
