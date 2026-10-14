import LearningErrorNotice from "./LearningErrorNotice";
import { learningDescription } from "../../utils/elearningPresentation";
import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BookOpen } from "lucide-react";
import * as commerce from "../../services/elearningCommerce";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import { resolveMediaUrl } from "../../utils/media";
import ELearningSkeleton from "./ELearningSkeleton";
import { checkoutStatus, openCheckout, paymentNotice, paymentsAvailable, testPayments } from "../../utils/learningPayments";
import EnrollmentCheckout, { PaymentStatus, TestModeBanner } from "./EnrollmentCheckout";
import "../../styles/admin/dashboard/elearning-commerce.css";

function useAccount(load) {
  const [data, setData] = useState(null), [error, setError] = useState(null), [refresh, setRefresh] = useState(0);
  useEffect(() => { let active = true; load().then(value => { if (active) { setData(value); setError(null); } }).catch(e => { if (active) setError(e); }); return () => { active = false; }; }, [load, refresh]);
  return { data, error, setError, retry: () => setRefresh(value => value + 1) };
}
function LearningLinks() {
  const { t } = useTranslation("dashboard");
  return <nav className="elearning-course-tabs"><Link to="/my-learning">{t("elearning.player.myLearning")}</Link><Link to="/my-learning/catalog">{t("elearning.commerce.catalog")}</Link><Link to="/my-learning/plans">{t("elearning.commerce.myPlans")}</Link></nav>;
}
export function Price({ terms }) {
  const { t } = useTranslation("dashboard");
  return <strong>{Number(terms.amount).toFixed(2)} {terms.currency} · {t(`elearning.commerce.${terms.billing_type}`)}</strong>;
}
export function Checkout({ checkout, local, onChange, onClose }) {
  const { t } = useTranslation("dashboard");
  const [busy, setBusy] = useState(false), [error, setError] = useState(null), [failed, setFailed] = useState(false);
  async function payment(state) {
    setBusy(true); setError(null);
    try { await commerce.localPaymentEvent(checkout.id, state); if (state === "paid") onChange(); else setFailed(true); }
    catch (e) { setError(e); } finally { setBusy(false); }
  }
  return <section className="ecommerce-list-card elearning-plan-card" aria-label={t("elearning.commerce.checkout")}>
    <h2>{t("elearning.commerce.checkout")}: {checkout.terms.name}</h2><Price terms={checkout.terms} />
    <p>{t("elearning.commerce.localOnly")}</p>{failed && <p role="status">{t("elearning.commerce.failedPayment")}</p>}{error && <LearningErrorNotice as="p">{t("elearning.commerce.error")}</LearningErrorNotice>}
    <div className="elearning-course-actions">{local && <><button className="ecommerce-primary-button" disabled={busy} onClick={() => payment("paid")}>{t("elearning.commerce.testPay")}</button><button className="ecommerce-secondary-button" disabled={busy} onClick={() => payment("failed")}>{t("elearning.commerce.testFail")}</button></>}<button className="ecommerce-secondary-button" disabled={busy} onClick={onClose}>{t("elearning.commerce.cancel")}</button></div>
  </section>;
}

export default function ELearningCatalog() {
  const { t, i18n } = useTranslation("dashboard"); const { labels } = useELearningTerminology(); const navigate = useNavigate();
  const state = useAccount(commerce.fetchCatalog);const [selected, setSelected] = useState(null), [checkout, setCheckout] = useState(null), [busy, setBusy] = useState(false);
  async function enroll(course) {
    setBusy(true); state.setError(null);
    try { await commerce.enrollCatalogCourse(course.id); navigate(`/my-learning/courses/${course.id}`); } catch (e) { state.setError(e); } finally { setBusy(false); }
  }
  async function buy(plan, course) {
    setBusy(true); state.setError(null);
    try { openCheckout(await commerce.createCheckout(plan.id, course?.id, crypto.randomUUID()), setCheckout); } catch (e) { state.setError(e); } finally { setBusy(false); }
  }
  if (!state.data && !state.error) return <ELearningSkeleton direction={i18n.dir()} label={t("elearning.commerce.loading")} />;
  return <><LearningLinks /><h1>{t("elearning.commerce.catalog")}</h1>{!checkout && !selected && <button className="ecommerce-secondary-button" onClick={() => setSelected({ name: t("elearning.commerce.accessPlans"), plans: state.data?.plans.map(p => p.id) || [] })}>{t("elearning.commerce.accessPlans")}</button>}{state.error && <LearningErrorNotice as="p">{t("elearning.commerce.error")} <button onClick={state.retry}>{t("elearning.retry")}</button></LearningErrorNotice>}
    {checkout ? <Checkout checkout={checkout} local={state.data.local_adapter} onClose={() => { setCheckout(null); state.retry(); }} onChange={() => { const course = checkout.requested_resource_id; setCheckout(null); setSelected(null); state.retry(); if (course) navigate(`/my-learning/courses/${course}`); }} /> : selected ? <section className="ecommerce-list-card elearning-plan-card">
      <h2>{t("elearning.commerce.choosePlan", { course: selected.name })}</h2>{state.data.plans.filter(p => selected.plans.includes(p.id)).map(plan => <article key={plan.id} className="elearning-plan-option"><h3>{plan.name}</h3><Price terms={plan} /><p>{t(`elearning.commerce.${plan.access_scope}`, { courses: labels.plural.course, course: labels.course })}</p><button className="ecommerce-primary-button" disabled={busy || !paymentsAvailable(state.data)} onClick={() => buy(plan, selected)}>{t("elearning.commerce.buy")}</button></article>)}
      <p>{t(paymentsAvailable(state.data) ? paymentNotice(state.data) : "elearning.commerce.providerUnavailable")}</p><button className="ecommerce-secondary-button" onClick={() => setSelected(null)}>{t("elearning.commerce.cancel")}</button>
    </section> : <div className="elearning-course-grid">{state.data?.courses.map(course => <article className="ecommerce-list-card elearning-plan-card" data-course-id={course.id} key={course.id}>
      <div className="elearning-course-cover">{course.cover_asset ? <img src={resolveMediaUrl(course.cover_asset)} alt="" /> : <BookOpen size={32} />}</div><h2>{course.name}</h2><p>{learningDescription(course.description)}</p>
      {course.cta.included_in && <p>{t("elearning.commerce.included", { name: course.cta.included_in.name })}</p>}
      {course.cta.action === "continue" ? <Link className="ecommerce-primary-button" to={`/my-learning/courses/${course.id}`}>{t("elearning.player.continue")}</Link> : ["enroll", "enroll_free"].includes(course.cta.action) ? <button className="ecommerce-primary-button" disabled={busy} onClick={() => enroll(course)}>{t(`elearning.commerce.${course.cta.action}`, { course: labels.course })}</button> : course.cta.action === "buy" ? <button className="ecommerce-primary-button" disabled={!course.plans.length} onClick={() => setSelected(course)}>{t("elearning.commerce.viewPlans")}</button> : <span className="elearning-course-status">{t(`elearning.commerce.${course.cta.action}`)}</span>}
    </article>)}</div>}
    {state.data?.courses.length === 0 && <p>{t("elearning.commerce.emptyCatalog")}</p>}
  </>;
}

export function MyLearningPlans() {
  const { t, i18n } = useTranslation("dashboard"); const state = useAccount(commerce.fetchMyPlans);
  const [checkout, setCheckout] = useState(null), [busy, setBusy] = useState(false), [payment, setPayment] = useState(null);
  const location = useLocation(), navigate = useNavigate();
  async function confirm(id, attempts = 1) {
    setBusy(true); setPayment("confirming");
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      try { await commerce.reconcileCheckout(id); setPayment("confirmed"); setBusy(false); return true; }
      catch { if (attempt < attempts) await new Promise(resolve => setTimeout(resolve, 2500)); }
    }
    setPayment("pending"); setBusy(false); return false;
  }
  useEffect(() => {
    const query = new URLSearchParams(location.search), id = query.get("checkout"), result = query.get("payment");
    if (!result) return;
    navigate(location.pathname, { replace: true });
    if (result === "cancelled") { queueMicrotask(() => setPayment("cancelled")); return; }
    if (result !== "success" || !id) return;
    // Webhooks normally arrive first; reconciliation reads provider truth if not.
    queueMicrotask(() => { void confirm(id, 6).then(done => {
      if (!done) return;
      state.retry();
      return commerce.fetchMyPlans().then(account => {
        const record = account.checkouts.find(item => item.id === id);
        if (record?.requested_resource_id) navigate(`/my-learning/courses/${record.requested_resource_id}`);
      }).catch(() => {});
    }); });
    // The URL is consumed once; state is read only for the post-payment destination.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.search]);
  async function lifecycle(id, action, cancel = false) {
    setBusy(true); state.setError(null);
    try { await commerce.localPaymentEvent(id, action, cancel); state.retry(); } catch (e) { state.setError(e); } finally { setBusy(false); }
  }
  if (!state.data && !state.error) return <ELearningSkeleton direction={i18n.dir()} label={t("elearning.commerce.loading")} />;
  // Opt-in academies show the document's payment states for every checkout.
  const gate = state.data?.enrollment_gate === true;
  return <><LearningLinks /><h1>{t("elearning.commerce.myPlans")}</h1>{state.error && <LearningErrorNotice as="p">{t("elearning.commerce.error")}</LearningErrorNotice>}
    {gate && testPayments(state.data) && <TestModeBanner />}
    {payment && (gate ? <PaymentStatus status={{ confirming: "processing", pending: "processing" }[payment] || payment} /> : <p role="status">{t(`elearning.commerce.payment_${payment}`)}</p>)}
    {checkout && (gate ? <EnrollmentCheckout checkout={checkout} local={state.data.local_adapter} testMode={testPayments(state.data)} referralCode={state.data.referral_code} courseId={checkout.requested_resource_id} onPaid={state.retry} onClose={() => setCheckout(null)} />
      : <Checkout checkout={checkout} local={state.data.local_adapter} onClose={() => setCheckout(null)} onChange={() => { setCheckout(null); state.retry(); }} />)}
    {!state.data?.entitlements.length && <p>{t("elearning.commerce.noPurchases")}</p>}
    <div className="elearning-course-grid">{state.data?.entitlements.map(ent => <article key={ent.id} className="ecommerce-list-card elearning-plan-card"><h2>{ent.terms.name}</h2><Price terms={ent.terms} /><p>{t(`elearning.commerce.${ent.effective_status}`)}</p>{ent.expires_at ? <p>{t(ent.cancel_at_period_end ? "elearning.commerce.endsAt" : "elearning.commerce.paidUntil", { date: new Date(ent.expires_at).toLocaleString(i18n.language) })}</p> : <p>{t("elearning.commerce.lifetime")}</p>}
      {state.data.local_adapter && ent.terms.billing_type !== "one_time" && <div className="elearning-course-actions"><button disabled={busy || ent.effective_status === "revoked"} onClick={() => lifecycle(ent.checkout_id, ent.effective_status === "active" ? "expired" : "active")}>{t(ent.effective_status === "active" ? "elearning.commerce.testExpire" : "elearning.commerce.testReactivate")}</button><button disabled={busy || ent.effective_status !== "active"} onClick={() => lifecycle(ent.checkout_id, "active", true)}>{t("elearning.commerce.testCancel")}</button></div>}
    </article>)}</div>
    {gate && state.data.checkouts.filter(c => !["pending", "failed"].includes(c.state)).map(c => <article className="ecommerce-list-card elearning-plan-card" key={c.id}><h2>{c.terms.name}</h2><Price terms={c.terms} /><PaymentStatus status={checkoutStatus(c.state)} /></article>)}
    {state.data?.checkouts.filter(c => c.state === "pending" || c.state === "failed").map(c => <article className="ecommerce-list-card elearning-plan-card" key={c.id}><h2>{c.terms.name}</h2><Price terms={c.terms} />{gate ? <PaymentStatus status={checkoutStatus(c.state)} /> : <p>{t(`elearning.commerce.${c.state}`)}</p>}{state.data.local_adapter ? <button onClick={() => setCheckout(c)}>{t("elearning.commerce.checkout")}</button> : <button disabled={busy || !state.data.payments_available} onClick={async () => { if (await confirm(c.id)) state.retry(); }}>{t("elearning.commerce.checkPayment")}</button>}</article>)}
  </>;
}
