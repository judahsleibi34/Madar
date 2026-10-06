import { learningDescription } from "../../utils/elearningPresentation";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BookOpen } from "lucide-react";
import * as commerce from "../../services/elearningCommerce";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import { resolveMediaUrl } from "../../utils/media";
import ELearningSkeleton from "./ELearningSkeleton";
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
    <p>{t("elearning.commerce.localOnly")}</p>{failed && <p role="status">{t("elearning.commerce.failedPayment")}</p>}{error && <p role="alert">{t("elearning.commerce.error")}</p>}
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
    try { setCheckout((await commerce.createCheckout(plan.id, course?.id, crypto.randomUUID())).checkout); } catch (e) { state.setError(e); } finally { setBusy(false); }
  }
  if (!state.data && !state.error) return <ELearningSkeleton direction={i18n.dir()} label={t("elearning.commerce.loading")} />;
  return <><LearningLinks /><h1>{t("elearning.commerce.catalog")}</h1>{!checkout && !selected && <button className="ecommerce-secondary-button" onClick={() => setSelected({ name: t("elearning.commerce.accessPlans"), plans: state.data?.plans.map(p => p.id) || [] })}>{t("elearning.commerce.accessPlans")}</button>}{state.error && <p role="alert">{t("elearning.commerce.error")} <button onClick={state.retry}>{t("elearning.retry")}</button></p>}
    {checkout ? <Checkout checkout={checkout} local={state.data.local_adapter} onClose={() => { setCheckout(null); state.retry(); }} onChange={() => { const course = checkout.requested_resource_id; setCheckout(null); setSelected(null); state.retry(); if (course) navigate(`/my-learning/courses/${course}`); }} /> : selected ? <section className="ecommerce-list-card elearning-plan-card">
      <h2>{t("elearning.commerce.choosePlan", { course: selected.name })}</h2>{state.data.plans.filter(p => selected.plans.includes(p.id)).map(plan => <article key={plan.id} className="elearning-plan-option"><h3>{plan.name}</h3><Price terms={plan} /><p>{t(`elearning.commerce.${plan.access_scope}`, { courses: labels.plural.course, course: labels.course })}</p><button className="ecommerce-primary-button" disabled={busy || !state.data.local_adapter} onClick={() => buy(plan, selected)}>{t("elearning.commerce.buy")}</button></article>)}
      {!state.data.local_adapter && <p>{t("elearning.commerce.providerUnavailable")}</p>}<button className="ecommerce-secondary-button" onClick={() => setSelected(null)}>{t("elearning.commerce.cancel")}</button>
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
  const [checkout, setCheckout] = useState(null), [busy, setBusy] = useState(false);
  async function lifecycle(id, action, cancel = false) {
    setBusy(true); state.setError(null);
    try { await commerce.localPaymentEvent(id, action, cancel); state.retry(); } catch (e) { state.setError(e); } finally { setBusy(false); }
  }
  if (!state.data && !state.error) return <ELearningSkeleton direction={i18n.dir()} label={t("elearning.commerce.loading")} />;
  return <><LearningLinks /><h1>{t("elearning.commerce.myPlans")}</h1>{state.error && <p role="alert">{t("elearning.commerce.error")}</p>}
    {checkout && <Checkout checkout={checkout} local={state.data.local_adapter} onClose={() => setCheckout(null)} onChange={() => { setCheckout(null); state.retry(); }} />}
    {!state.data?.entitlements.length && <p>{t("elearning.commerce.noPurchases")}</p>}
    <div className="elearning-course-grid">{state.data?.entitlements.map(ent => <article key={ent.id} className="ecommerce-list-card elearning-plan-card"><h2>{ent.terms.name}</h2><Price terms={ent.terms} /><p>{t(`elearning.commerce.${ent.effective_status}`)}</p>{ent.expires_at ? <p>{t(ent.cancel_at_period_end ? "elearning.commerce.endsAt" : "elearning.commerce.paidUntil", { date: new Date(ent.expires_at).toLocaleString(i18n.language) })}</p> : <p>{t("elearning.commerce.lifetime")}</p>}
      {state.data.local_adapter && ent.terms.billing_type !== "one_time" && <div className="elearning-course-actions"><button disabled={busy || ent.effective_status === "revoked"} onClick={() => lifecycle(ent.checkout_id, ent.effective_status === "active" ? "expired" : "active")}>{t(ent.effective_status === "active" ? "elearning.commerce.testExpire" : "elearning.commerce.testReactivate")}</button><button disabled={busy || ent.effective_status !== "active"} onClick={() => lifecycle(ent.checkout_id, "active", true)}>{t("elearning.commerce.testCancel")}</button></div>}
    </article>)}</div>
    {state.data?.checkouts.filter(c => c.state === "pending" || c.state === "failed").map(c => <article className="ecommerce-list-card elearning-plan-card" key={c.id}><h2>{c.terms.name}</h2><Price terms={c.terms} /><p>{t(`elearning.commerce.${c.state}`)}</p><button disabled={!state.data.local_adapter} onClick={() => setCheckout(c)}>{t("elearning.commerce.checkout")}</button></article>)}
  </>;
}
