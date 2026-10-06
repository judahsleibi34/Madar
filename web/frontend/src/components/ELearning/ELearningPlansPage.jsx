import ELearningDescriptionTextarea from "./ELearningDescriptionTextarea";
import { useEffect, useRef, useState } from "react";
import { CreditCard, Plus } from "lucide-react";
import { useTranslation } from "react-i18next";
import { fetchPlans, savePlan } from "../../services/elearningCommerce";
import { fetchCourses } from "../../services/elearningCourses";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import ELearningSkeleton from "./ELearningSkeleton";
import "../../styles/admin/dashboard/elearning-commerce.css";

const supportedCurrencies = ["ILS", "JOD", "USD", "EUR"];
const empty = { name: "", description: "", status: "draft", billing_type: "one_time", amount: "20.00", currency: "USD", access_scope: "single_course", course_ids: [], revision: 1 };
export default function ELearningPlansPage() {
  const { t, i18n } = useTranslation("dashboard");
  const { labels } = useELearningTerminology();
  const [plans, setPlans] = useState(null), [courses, setCourses] = useState([]), [form, setForm] = useState(null), [error, setError] = useState(null), [busy, setBusy] = useState(false);
  const dialog = useRef(null);
  useEffect(() => {
    let active = true;
    async function load() {
      const [data, first] = await Promise.all([fetchPlans(), fetchCourses()]);
      const all = [...first.courses]; let hasMore = first.has_more;
      while (hasMore) { const next = await fetchCourses(all.length); all.push(...next.courses); hasMore = next.has_more; }
      if (active) { setPlans(data.plans); setCourses(all.filter(c => c.status !== "archived" && c.access_type !== "private" && c.catalog_visible !== false)); }
    }
    load().catch(e => { if (active) setError(e); });
    return () => { active = false; };
  }, []);
  useEffect(() => { if (form) dialog.current?.showModal(); }, [form]);
  const createPlan = () => { setError(null); setForm({ ...empty }); };
  const update = (key, value) => setForm(old => ({ ...old, [key]: value }));
  async function save(event) {
    event.preventDefault(); setBusy(true); setError(null);
    try { const data = await savePlan(form); setPlans(data.plans); setForm(null); } catch (e) { setError(e); } finally { setBusy(false); }
  }
  if (!plans && !error) return <ELearningSkeleton label={t("elearning.commerce.loading")} direction={i18n.dir()} />;
  return <main className="ecommerce-page elearning-management" dir={i18n.dir()}>
    <header className="ecommerce-page-header app-page-intro"><div><h1>{t("elearning.academy.learningPlans")}</h1><p>{t("elearning.academy.pricingHelp")}</p></div><button className="ecommerce-primary-button" onClick={createPlan}>{t("elearning.commerce.addPlan")}</button></header>
    {error && !form && <p role="alert">{t("elearning.commerce.error")}</p>}
    {plans?.length === 0 && !error && <section className="ecommerce-list-card ecommerce-empty-state elearning-plans-empty" aria-labelledby="learning-plans-empty-title">
      <span className="elearning-plans-empty-icon"><CreditCard size={32} aria-hidden="true" /></span>
      <h2 id="learning-plans-empty-title">{t("elearning.commerce.plansEmptyTitle")}</h2>
      <p>{t("elearning.commerce.plansEmptyHelp", { courses: labels.plural.course })}</p>
      <button type="button" className="ecommerce-primary-button" onClick={createPlan}><Plus size={18} aria-hidden="true" />{t("elearning.commerce.createFirstPlan")}</button>
    </section>}
    <div className="elearning-course-grid">{plans?.map(plan => <article className="ecommerce-list-card elearning-plan-card" key={plan.id}>
      <h2>{plan.name}</h2><p>{plan.description}</p><strong>{plan.amount} {plan.currency} · {t(`elearning.commerce.${plan.billing_type}`)}</strong>
      <p>{t(`elearning.commerce.${plan.access_scope}`, { courses: labels.plural.course, course: labels.course })}</p><span className="elearning-course-status">{t(`elearning.commerce.${plan.status}`)}</span>
      <button className="ecommerce-secondary-button" onClick={() => { setError(null); setForm({ ...plan }); }}>{t("elearning.commerce.editPlan")}</button>
    </article>)}</div>
    {form && <dialog ref={dialog} className="ecommerce-modal elearning-dialog elearning-plan-dialog" aria-labelledby="learning-plan-title" onCancel={event => { if (busy) event.preventDefault(); else setForm(null); }}>
      <form onSubmit={save} className="elearning-plan-form"><h2 id="learning-plan-title">{t(form.id ? "elearning.commerce.editPlan" : "elearning.commerce.addPlan")}</h2>
        {error && <p role="alert">{t("elearning.commerce.error")}</p>}
        <label className="elearning-field">{t("elearning.commerce.name")}<input value={form.name} maxLength={120} required onChange={e => update("name", e.target.value)} /></label>
        <label className="elearning-field">{t("elearning.commerce.description")}<ELearningDescriptionTextarea label={t("elearning.commerce.description")} value={form.description} maxLength={4000} onChange={e => update("description", e.target.value)} /></label>
        <div className="elearning-plan-options">
        <div className="ecommerce-field-grid">
          <label className="elearning-field">{t("elearning.commerce.billingType")}<select aria-label={t("elearning.commerce.billingType")} value={form.billing_type} onChange={e => update("billing_type", e.target.value)}>{["one_time", "monthly", "yearly"].map(value => <option key={value} value={value}>{t(`elearning.commerce.${value}`)}</option>)}</select></label>
          <label className="elearning-field">{t("elearning.commerce.accessScope")}<select aria-label={t("elearning.commerce.accessScope")} value={form.access_scope} onChange={e => setForm(old => ({ ...old, access_scope: e.target.value, course_ids: [] }))}>{["single_course", "selected_courses", "all_courses"].map(value => <option key={value} value={value}>{t(`elearning.commerce.${value}`, { courses: labels.plural.course, course: labels.course })}</option>)}</select></label>
          <label className="elearning-field">{t("elearning.commerce.price")}<input type="number" min="0.01" step="0.01" required value={form.amount} onChange={e => update("amount", e.target.value)} /></label>
          <label className="elearning-field">{t("elearning.commerce.currency")}<select required value={form.currency} onChange={e => update("currency", e.target.value)}>{!supportedCurrencies.includes(form.currency) && <option value={form.currency} disabled>{form.currency}</option>}{supportedCurrencies.map(code => <option key={code} value={code}>{t(`commerce:admin.${code.toLowerCase()}`)}</option>)}</select></label>
        </div>
        {form.access_scope === "all_courses" ? <p>{t("elearning.commerce.futurePolicy", { courses: labels.plural.course })}</p> : <fieldset className="elearning-plan-courses"><legend>{t("elearning.commerce.chooseCourses", { courses: labels.plural.course })}</legend>{courses.map(course => <label className="elearning-course-choice" key={course.id}><input type="checkbox" name="plan-course" value={course.id} checked={form.course_ids.includes(course.id)} onChange={e => update("course_ids", form.access_scope === "single_course" ? e.target.checked ? [course.id] : [] : e.target.checked ? [...form.course_ids, course.id] : form.course_ids.filter(id => id !== course.id))} /><span>{course.name}</span></label>)}</fieldset>}
        </div>
        <label className="elearning-field">{t("elearning.commerce.saleStatus")}<select aria-label={t("elearning.commerce.saleStatus")} value={form.status} onChange={e => update("status", e.target.value)}>{["draft", "active", "archived"].map(value => <option value={value} key={value}>{t(`elearning.commerce.planStatusOptions.${value}`)}</option>)}</select></label>
        <p className="elearning-plan-status-help">{t(`elearning.commerce.planStatusHelp.${form.status}`)}</p>
        <footer className="elearning-course-actions"><button type="button" className="ecommerce-secondary-button" disabled={busy} onClick={() => setForm(null)}>{t("elearning.commerce.cancel")}</button><button className="ecommerce-primary-button" aria-busy={busy} disabled={busy || (form.access_scope !== "all_courses" && !form.course_ids.length)}>{t(busy ? "elearning.saving" : "elearning.commerce.save")}</button></footer>
      </form>
    </dialog>}
  </main>;
}
