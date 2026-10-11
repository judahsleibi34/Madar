import { useCallback, useEffect, useRef, useState } from "react";
import AcademySupportDocuments from "./AcademySupportDocuments";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { request } from "./academyProgrammeApi";
import AcademyProgrammeOwner from "./AcademyProgrammeOwner";

const fields = {
  affiliate: ["full_name", "email", "country", "experience", "promotion_plan", "additional_information"],
  tuition: ["full_name", "university", "student_number", "contact", "tuition_fee", "financial_difficulty", "requested_amount", "supporting_information"],
};
const transitions = row => row.payment_method
  ? ({ pending: ["approved", "rejected"], approved: ["processing", "rejected"], processing: ["paid", "rejected"] }[row.status] || [])
  : ({ submitted: ["under_review", "approved", "not_approved"], under_review: ["approved", "not_approved"], approved: row.kind === "affiliate" ? ["suspended"] : [], suspended: row.kind === "affiliate" ? ["approved"] : [] }[row.status] || []);

function LearnerProgrammesPage({ admin = false, initialKind = "affiliate", affiliateOnly = false }) {
  const { t, i18n } = useTranslation("dashboard");
  const label = key => t(`elearning.programmes.${key}`);
  const location = useLocation();
  const requestedKind = new URLSearchParams(location.search).get("kind");
  const [kind, setKind] = useState(!affiliateOnly && ["affiliate", "tuition", "exchange", "withdrawal"].includes(requestedKind) ? requestedKind : initialKind);
  const opportunity = new URLSearchParams(location.search).get("opportunity_id");
  const generation = useRef(0);
  const [requestKey, setRequestKey] = useState(() => crypto.randomUUID());
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState(false);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(0);
  const [profile, setProfile] = useState(null);
  const [selected, setSelected] = useState(null);
  const load = useCallback(async () => {
    const current = ++generation.current;
    setError(false);
    try {
      const path = admin ? `/management/${kind === "withdrawal" ? "withdrawal" : "application"}?limit=50&offset=${page * 50}${kind === "withdrawal" ? "" : `&kind=${kind}`}${status ? `&status=${status}` : ""}${opportunity ? `&opportunity_id=${encodeURIComponent(opportunity)}` : ""}` : "/account";
      const result = await request(path);
      if (generation.current === current) {
        setData(result);
        if (!admin && !affiliateOnly && result.capabilities && !result.capabilities[kind]) {
          const first = ['affiliate', 'tuition', 'exchange', 'withdrawal'].find(key => result.capabilities[key]);
          if (first) setKind(first);
        }
      }
    } catch (failure) { if (generation.current === current) setError(failure.code === "academy_programmes_disabled" ? "disabled" : true); }
  }, [admin, affiliateOnly, kind, page, status, opportunity]);
  useEffect(() => { const timer = window.setTimeout(load, 0); return () => { window.clearTimeout(timer); generation.current += 1; }; }, [load]);
  async function inspect(row) {
    setSelected(row); setProfile(null);
    if (data?.capabilities && !data.capabilities.wallet) return;
    try { const result = await request(`/management/members/${row.user_id}`); setProfile({ userId: row.user_id, data: result }); } catch { setError(true); }
  }
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(false); setSuccess(false);
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    try {
      if (admin) await request(`/management/${kind === "withdrawal" ? "withdrawal" : "application"}/${selected.id}/review`, { status: values.status, revision: selected.revision, note: values.note });
      else if (kind === "withdrawal") await request("/withdrawals", { amount: values.amount, payment_method: values.payment_method, payment_information: values.payment_information, ownership_confirmed: values.ownership_confirmed === "on", idempotency_key: form.dataset.requestKey });
      else await request("/applications", { kind, details: { ...values, terms_accepted: values.terms_accepted === "on" }, idempotency_key: form.dataset.requestKey });
      form.reset(); setRequestKey(crypto.randomUUID()); setSelected(null); setSuccess(true); await load();
    } catch { setError(true); } finally { setBusy(false); }
  }
  const rows = admin ? data?.items || [] : kind === "withdrawal" ? data?.withdrawals || [] : (data?.applications || []).filter(row => row.kind === kind);
  const openAffiliate = kind === "affiliate" && rows.find(row => ["submitted", "under_review", "approved", "suspended"].includes(row.status));
  const wallet = data?.wallet;
  const eligibility = data?.eligibility || wallet;
  const configured = key => Boolean(data && (!data.capabilities || data.capabilities[key]) && data.settings?.[({ affiliate: "affiliates_enabled", tuition: "tuition_support_enabled", exchange: "exchange_programme_enabled", withdrawal: "withdrawals_enabled" })[key]]);
  const enabled = configured(kind) && (kind === "withdrawal" ? data?.settings?.withdrawals_enabled && Number(wallet?.available) >= Number(data?.settings?.minimum_withdrawal_amount) : kind === "tuition" ? eligibility?.tuition_eligible : kind === "exchange" ? eligibility?.exchange_eligible : data?.settings?.affiliates_enabled) && (kind !== "withdrawal" || (data.settings.minimum_withdrawal_amount != null && data.settings.withdrawal_methods?.length > 0 && Number(wallet?.debt || 0) === 0));
  return <section className="ecommerce-page elearning-management" dir={i18n.dir()}>
    <header className="ecommerce-page-header app-page-intro"><h1>{affiliateOnly ? t("elearning.affiliate.application") : label("title")}</h1><p>{label(admin ? "adminHelp" : "help")}</p></header>
    <nav className="elearning-course-actions" aria-label={label("title")}>{(affiliateOnly ? [] : ["affiliate", "tuition", "exchange", "withdrawal"]).filter(key => configured(key)).map(value => <button type="button" className={kind === value ? "ecommerce-primary-button" : "ecommerce-secondary-button"} key={value} onClick={() => { setKind(value); setRequestKey(crypto.randomUUID()); setPage(0); setSelected(null); setSuccess(false); }}>{value === "tuition" ? data?.settings?.support_programme_name || label("support") : value === "exchange" ? data?.settings?.exchange_programme_name || label(value) : label(value)}</button>)}</nav>
    {error && <p role="alert">{label(error === "disabled" ? "enableHelp" : "error")} {error === "disabled" && admin && <Link to="/e-learning/settings">{label("settings")}</Link>} <button className="ecommerce-secondary-button" onClick={load}>{t("elearning.retry")}</button></p>}
    {data && !["affiliate", "tuition", "exchange", "withdrawal"].some(configured) && <p role="status">{t("elearning.player.unavailable")}</p>}
    {openAffiliate && <p role="status">{label(openAffiliate.status)} · <Link to="/my-learning/affiliate">{t("elearning.affiliate.dashboard")}</Link></p>}
    {success && <p role="status">{label("saved")}</p>}
    {!data && !error && <p role="status">{t("elearning.loading")}</p>}
    {!admin && kind === "withdrawal" && wallet && <div className="ecommerce-list-card"><h2>{label("wallet")}</h2><dl>{["available", "pending", "total_earned", "total_withdrawn", "debt"].map(key => <div key={key}><dt>{label(key)}</dt><dd>{wallet[key]} {wallet.currency}</dd></div>)}</dl><p>{label("sales")}: {wallet.verified_sales}{wallet.threshold != null && <> / {wallet.threshold} · {label("remaining")}: {wallet.remaining_sales}</>}</p>{wallet.tuition_eligible != null && <p>{label(wallet.tuition_eligible ? "eligible" : "locked")}</p>}</div>}
    {admin && <div className="settings-form-grid"><label>{label("search")}<input value={search} onChange={event => setSearch(event.target.value)} /></label><label>{label("status")}<select value={status} onChange={event => { setStatus(event.target.value); setPage(0); }}><option value="">{label("all")}</option>{["submitted", "under_review", "approved", "not_approved", "suspended", "pending", "processing", "paid", "rejected"].map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label></div>}
    <div className="elearning-course-grid">{rows.filter(row => !search || `${row.id} ${row.user_id} ${JSON.stringify(row.details || {})}`.toLowerCase().includes(search.toLowerCase())).map(row => <article className="ecommerce-list-card" key={row.id}>
      <h3>{row.details?.full_name || `${label("user")} ${row.user_id}`}</h3><p>{label(row.status)} · {new Date(row.created_at).toLocaleString(i18n.language)}</p>{row.amount && <p>{row.amount} {row.currency} · {row.payment_method}</p>}{!admin && <details><summary>{label("history")}</summary><table className="learner-data-table"><tbody>{Object.entries(row.details || {}).filter(([key]) => key !== "terms_accepted").map(([key, value]) => <tr key={key}><th scope="row">{label(key)}</th><td>{String(value)}</td></tr>)}</tbody></table>{row.payment_information && <p style={{ whiteSpace: "pre-wrap" }}>{row.payment_information}</p>}</details>}
      {admin && <button type="button" className="ecommerce-secondary-button" disabled={busy} onClick={() => inspect(row)}>{label("review")}</button>}
      {!admin && row.kind === "tuition" && <AcademySupportDocuments application={row} editable={["submitted", "under_review"].includes(row.status)} />}
    </article>)}</div>
    {!admin && kind === 'exchange' && <p><Link className="ecommerce-primary-button" to="/my-learning/exchange">{t('elearning.exchange.opportunities')}</Link> · {t('elearning.exchange.legacy')}</p>}
    {data && !rows.length && <p>{label("empty")}</p>}
    {admin && <div className="elearning-course-actions"><button disabled={!page} onClick={() => setPage(page - 1)}>{label("previous")}</button><button disabled={rows.length < 50} onClick={() => setPage(page + 1)}>{label("next")}</button></div>}
    {data && !admin && ["tuition", "exchange"].includes(kind) && configured(kind) && <div className="ecommerce-list-card"><h2>{kind === "tuition" ? data.settings.support_programme_name || label("support") : data.settings.exchange_programme_name || label("exchange")}</h2><p>{label(enabled ? "eligible" : "locked")}</p>{kind === "tuition" && eligibility?.threshold != null && <p>{label("sales")}: {eligibility.verified_sales} / {eligibility.threshold} · {label("remaining")}: {eligibility.remaining_sales}</p>}</div>}
    {data && (!admin ? !openAffiliate && kind !== "exchange" && configured(kind) && (kind !== "withdrawal" || wallet) : selected) && <form key={`${kind}:${selected?.id || "new"}:${success}`} data-request-key={requestKey} onSubmit={submit} className="settings-card">
      {admin && kind === "tuition" && <AcademySupportDocuments application={selected} />}
      {admin ? <><h2>{label("review")}</h2>{profile?.userId === selected.user_id && <div><h3>{profile.data.user.name} · {profile.data.user.email}</h3><p>{label("role")}: {profile.data.role}</p><p>{label("sales")}: {profile.data.wallet.verified_sales}{profile.data.wallet.threshold != null && <> / {profile.data.wallet.threshold}</>}</p><p>{label("available")}: {profile.data.wallet.available} {profile.data.wallet.currency}</p><p>{label("referrals")}: {profile.data.referrals.length} · {label("withdrawal")}: {profile.data.withdrawals.length} · {label("transactions")}: {profile.data.transactions.length}</p><details><summary>{label("history")}</summary>{profile.data.history.map(row => <p key={row.id}>{label(row.new_status)} · {row.note} · {new Date(row.created_at).toLocaleString(i18n.language)} · {label("user")} {row.actor_id}</p>)}</details></div>}<dl>{Object.entries(selected.details || {}).map(([key, value]) => <div key={key}><dt>{label(key)}</dt><dd>{String(value)}</dd></div>)}</dl>{selected.payment_information && <p>{selected.payment_information}</p>}
        <label>{label("status")}<select name="status" required>{transitions(selected).map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label><p style={{ whiteSpace: "pre-wrap" }}>{selected?.terms_snapshot}</p><label>{label("note")}<textarea name="note" required maxLength={4000} /></label>
      </> : kind === "withdrawal" ? <><p>{t("elearning.learner.minimumWithdrawal")}: {data.settings.minimum_withdrawal_amount} {wallet.currency}</p><label>{label("amount")}<input name="amount" type="number" step="0.01" min={data.settings.minimum_withdrawal_amount} max={wallet.available} required /></label><label>{label("payment_method")}<select name="payment_method">{data.settings.withdrawal_methods.map(value => <option key={value}>{value}</option>)}</select></label><label>{label("payment_information")}<textarea name="payment_information" required maxLength={4000} /></label><label><input type="checkbox" name="ownership_confirmed" required />{label("ownership_confirmed")}</label></> : <>{fields[kind].map(key => <label className="elearning-field" key={key}>{label(key)}<textarea name={key} required={!key.includes("information") || (key === "supporting_information" && data.settings.tuition_support_information_required)} maxLength={4000} /></label>)}<p style={{ whiteSpace: "pre-wrap" }}>{data.settings[`${kind}_terms`]}</p><label><input type="checkbox" name="terms_accepted" required />{label("terms_accepted")}</label></>}
      <button className="ecommerce-primary-button" disabled={busy || (admin ? !transitions(selected).length : !enabled)}>{label(busy ? "saving" : "submit")}</button>
    </form>}
  </section>;
}

export default function AcademyProgrammesPage(props){return props.admin?<AcademyProgrammeOwner kind={props.initialKind || "affiliate"} responseId={props.responseId} />:<LearnerProgrammesPage {...props}/>;}
