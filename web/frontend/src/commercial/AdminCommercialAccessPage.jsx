import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiFetch, getApiUrl, readApiError, readApiResponse } from "../utils/apiClient";

import { parseUsdMinor, money } from "./money";

const operations = { "manual-payments": "Record manual payment", "complimentary-grants": "Grant complimentary access", "payment-corrections": "Correct a receipt", revocations: "Revoke commercial access", "review-inactive": "Review with no active plan" };
const localTime = () => {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
};

export default function AdminCommercialAccessPage() {
  const { tenantId } = useParams();
  const [data, setData] = useState(null);
  const [plans, setPlans] = useState([]);
  const [queue, setQueue] = useState({ tenants: [], total: 0 });
  const [offset, setOffset] = useState(0);
  const [operation, setOperation] = useState("manual-payments");
  const [fields, setFields] = useState(() => ({ plan_id: "", method: "cash", amount: "", currency: "USD", billing_months: "1", paid_at: localTime(), valid_from: localTime(), valid_until: "", receipt_reference: "", reason: "", override_reason: "", period_id: "", payment_id: "", supersedes_period_id: "" }));
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const commandRef = useRef(null);
  const load = useCallback(async (signal) => {
    const endpoint = tenantId ? `/admin/commercial/tenants/${tenantId}?offset=${offset}&limit=50` : `/admin/commercial/review?offset=${offset}&limit=50`;
    const response = await apiFetch(getApiUrl(endpoint), { cache: "no-store", signal });
    const body = await readApiResponse(response);
    if (!response.ok) throw new Error(readApiError(body, "Commercial access could not be loaded. Administrator MFA is required."));
    if (tenantId) setData(body); else setQueue(body);
  }, [tenantId, offset]);
  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).catch((failure) => { if (!controller.signal.aborted) setError(failure.message); });
    apiFetch(getApiUrl("/billing/catalog"), { cache: "no-store", signal: controller.signal })
      .then(readApiResponse).then((body) => { if (!controller.signal.aborted) setPlans((body?.catalog?.products || []).filter((product) => product.type === "base_plan")); }).catch(() => {});
    return () => controller.abort();
  }, [load]);
  const set = (name, value) => setFields((previous) => ({ ...previous, [name]: value }));
  const isPayment = operation === "manual-payments";
  const isGrant = isPayment || operation === "complimentary-grants";
  const isCorrection = operation === "payment-corrections";
  const plan = plans.find((product) => product.id === fields.plan_id);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(""); setNotice("");
    try {
      const command = { reason: fields.reason };
      if (isGrant) {
        Object.assign(command, { plan_id: fields.plan_id, valid_from: new Date(fields.valid_from).toISOString(), valid_until: new Date(fields.valid_until).toISOString() });
        if (fields.supersedes_period_id) command.supersedes_period_id = fields.supersedes_period_id;
      }
      if (isPayment || isCorrection) {
        Object.assign(command, { actual_minor: parseUsdMinor(fields.amount), paid_at: new Date(fields.paid_at).toISOString(), receipt_reference: fields.receipt_reference });
        if (fields.override_reason) command.override_reason = fields.override_reason;
      }
      if (isPayment) Object.assign(command, { method: fields.method, currency: "USD", billing_months: Number(fields.billing_months) });
      if (isCorrection) command.payment_id = fields.payment_id;
      if (operation === "revocations") command.period_id = fields.period_id;
      const fingerprint = JSON.stringify({ tenantId, operation, command });
      if (commandRef.current?.fingerprint !== fingerprint) commandRef.current = { fingerprint, key: crypto.randomUUID() };
      command.idempotency_key = commandRef.current.key;
      const response = await apiFetch(getApiUrl(`/admin/commercial/tenants/${tenantId}/${operation}`), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(command) });
      const body = await readApiResponse(response);
      if (!response.ok) throw new Error(readApiError(body, "Command was not accepted."));
      setNotice("Commercial command recorded. Repeating the same request returns this result.");
      await load();
    } catch (failure) {
      setError(failure.message || "The result could not be confirmed. Retry the unchanged request to check its original result.");
    } finally { setBusy(false); }
  }
  const input = (label, name, type = "text", required = true) => <label>{label}<input type={type} value={fields[name]} required={required} onChange={(event) => set(name, event.target.value)} maxLength={name === "receipt_reference" ? 200 : undefined} /></label>;
  return <main className="user-management-page commercial-access-page">
    <header><h1>{tenantId ? `Commercial access · Workspace ${tenantId}` : "Commercial review queue"}</h1><Link to="/admin/users">User management</Link> · <Link to="/admin/commercial">Review queue</Link></header>
    {error && <div role="alert"><p>{error}</p><Link to="/settings/security">Verify administrator MFA</Link></div>}
    {notice && <p role="status">{notice}</p>}
    {!tenantId && <><p>{queue.total || 0} active workspaces require a commercial decision.</p><ul>{queue.tenants.map((tenant) => <li key={tenant.tenant_id}><Link to={`/admin/commercial/${tenant.tenant_id}`}>Workspace {tenant.tenant_id}</Link> · Needs review</li>)}</ul></>}
    {tenantId && data && <>
      <dl><dt>Status</dt><dd>{data.entitlements.commercial_status}</dd><dt>Plan</dt><dd>{data.entitlements.plan_id || "No proven active plan"}</dd><dt>Source</dt><dd>{data.commercial.period?.source_type || "No active period"}</dd><dt>Valid from</dt><dd>{data.commercial.period?.valid_from || "—"}</dd><dt>Paid through</dt><dd>{data.commercial.period?.valid_until || "—"}</dd><dt>Capabilities</dt><dd>{data.entitlements.capabilities.join(", ") || "None"}</dd></dl>
      <form onSubmit={submit} className="commercial-command-form">
        <label>Action<select aria-label="Action" value={operation} onChange={(event) => setOperation(event.target.value)}>{Object.entries(operations).map(([value,label]) => <option key={value} value={value}>{label}</option>)}</select></label>
        {isGrant && <><label>Plan<select aria-label="Plan" required value={fields.plan_id} onChange={(event) => set("plan_id",event.target.value)}><option value="">Select a reviewed plan</option>{plans.map((product) => <option key={product.id} value={product.id}>{product.name}</option>)}</select></label>{input("Valid from", "valid_from", "datetime-local")}{input("Paid through", "valid_until", "datetime-local")}{input("Period to supersede (optional)", "supersedes_period_id", "text", false)}</>}
        {isPayment && <><label>Payment method<select aria-label="Payment method" value={fields.method} onChange={(event) => set("method",event.target.value)}><option value="cash">Cash</option><option value="bank_transfer">Bank transfer</option><option value="other_manual">Other manual</option></select></label><label>Billing months<input type="number" min="1" max="120" step="1" required value={fields.billing_months} onChange={(event) => set("billing_months",event.target.value)} /></label><p>Expected price: {plan && /^\d+$/.test(fields.billing_months) ? money(BigInt(plan.price_minor) * BigInt(fields.billing_months)) : "Select a plan"}</p></>}
        {(isPayment || isCorrection) && <>{input("Actual amount (USD)", "amount")}{input("Paid at", "paid_at", "datetime-local")}{input("Receipt / reference", "receipt_reference")}{input("Amount or period override reason (required for exceptions)", "override_reason", "text", false)}</>}
        {isCorrection && <>{input("Original or latest corrected receipt ID", "payment_id")}<p>A receipt correction retains the original record and does not change access dates. Adjust access with a separate grant or revocation.</p></>}
        {operation === "revocations" && input("Access period ID", "period_id")}
        <label>Reason / notes<textarea required minLength={3} maxLength={1000} value={fields.reason} onChange={(event) => set("reason",event.target.value)} /></label>
        <label><input type="checkbox" required /> I reviewed this workspace, the amount or grant, and its access period.</label>
        <p>This action requires your current administrator session to have completed MFA.</p>
        <button type="submit" disabled={busy}>{busy ? "Recording…" : operations[operation]}</button>
      </form>
      {Object.entries(data.history).map(([kind, rows]) => <section key={kind}><h2>{kind}</h2><table><thead><tr><th>Reference</th><th>Details</th><th>Recorded</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id}><td><code>{row.id}</code></td><td>{kind === "payments" ? <>{row.method} · {money(row.actual_minor)} · Expected {money(row.expected_minor)}{row.corrects_payment_id && <> · Corrects {row.corrects_payment_id}</>}</> : kind === "periods" ? <>{row.plan_id} · {row.valid_from} → {row.valid_until}{row.revoked_at && <> · Revoked effective {row.revoked_at}</>}</> : <>{row.operation} · Actor {row.actor_user_id} · Revision {row.revision}</>}</td><td>{row.created_at}</td></tr>)}</tbody></table></section>)}
    </>}
    <nav aria-label="Commercial history pages"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0,offset-50))}>Previous</button><span> Page {offset / 50 + 1} </span><button disabled={tenantId ? !data?.history_has_more : offset+50 >= queue.total} onClick={() => setOffset(offset+50)}>Next</button></nav>
  </main>;
}
