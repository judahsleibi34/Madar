import { Link, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { learningFormsApi } from "../../ELearning/learningFormsApi";
import { fetchELearningSettings } from "../../../services/elearningSettings";
import { fetchAcademy } from "../../../services/elearningAcademy";
import { useTranslation } from "react-i18next";
export default function AcademyDataInspector({ element, onChange }) {
  const location = useLocation();
  const returnQuery = `?returnTo=${encodeURIComponent(location.pathname)}`;
  const { t, i18n } = useTranslation("dashboard");
  const [state, setState] = useState({ loading: true }), [attempt, setAttempt] = useState(0);
  useEffect(() => { let active = true; fetchELearningSettings().then(settings => {
    const address = settings.academy_management?.subdomain || settings.academy?.subdomain;
    if (!address) throw new Error("Academy address unavailable");
    return element.type === "academyForm" ? learningFormsApi().then(result => ({ forms:result.items })) : fetchAcademy(address);
  }).then(data => { if (active) setState({ attempt, data }); }).catch(() => { if (active) setState({ attempt, error: true }); }); return () => { active = false; }; }, [attempt, element.type]);
  const current = state.attempt === attempt ? state : { loading: true };
  const data = current.data;
  const config = element.academy || {};
  const update = value => onChange({ academy: { ...config, ...value } });
  if (element.type === "academyForm") return <fieldset dir={i18n.dir()} lang={i18n.language} className="academy-content-inspector"><legend>{t("elearning.ui.form_component")}</legend>{current.loading && <p role="status">{t("elearning.forms.loading")}</p>}{current.error && <><p role="alert">{t("elearning.forms.error")}</p><button type="button" onClick={()=>setAttempt(v=>v+1)}>{t("elearning.retry")}</button></>}{data && !data.forms.filter(form=>form.status!=="archived").length ? <><p>{t("elearning.ui.no_forms")}</p><p>{t("elearning.ui.builder_no_forms_help")}</p><Link className="ecommerce-primary-button" to={`/e-learning/forms/new${returnQuery}`}>{t("elearning.forms.create")}</Link></> : <><label>{t("elearning.forms.select")}<select disabled={!data} value={config.formId || ""} onChange={event => update({formId:event.target.value})}><option value="">{t("elearning.forms.select")}</option>{(data?.forms || []).filter(form => form.status !== "archived").map(form => <option key={form.id} value={form.id}>{form.name}</option>)}</select></label>{config.formId&&<Link className="ecommerce-secondary-button" to={`/e-learning/forms/${config.formId}/edit${returnQuery}`} target="_blank" rel="noopener noreferrer">{t("elearning.forms.edit")}</Link>}<Link to={`/e-learning/forms/new${returnQuery}`}>{t("elearning.forms.create")}</Link></>}</fieldset>;
  const plan = element.type === "academyPlans";
  const instructor = element.type === "academyInstructors";
  const key = plan ? "planIds" : instructor ? "instructorIds" : "courseIds";
  const items = data ? (plan ? data.plans : instructor ? data.instructors || [] : data.courses) : [];
  return <fieldset className="academy-content-inspector"><legend>Academy content</legend>
    <label>Heading<input value={config.heading || ""} onChange={event => update({ heading: event.target.value })} /></label>
    <label>Description<textarea value={config.description || ""} onChange={event => update({ description: event.target.value })} /></label>
    <label>Maximum items<input type="number" min="1" max="24" value={config.maxItems || 4} onChange={event => update({ maxItems: Math.max(1, Math.min(24, Number(event.target.value) || 4)) })} /></label>
    <label>Layout<select value={config.variant || "grid"} onChange={event => update({ variant: event.target.value })}><option value="grid">Grid</option><option value="compact">Compact</option></select></label>
    {element.type === "academyContinueLearning" ? <p>{t("elearning.academy.builderData.continue")}</p> : <fieldset className="academy-content-choices"><legend>{plan ? "Public plans" : instructor ? "Public instructors" : t("elearning.academy.builderData.availableCourses")}</legend>
      {!plan && !instructor && <p>{t("elearning.academy.builderData.courseSelectionHelp")}</p>}
      {current.loading && <p role="status">{t("elearning.academy.builderData.selectionLoading")}</p>}
      {current.error && <><p role="alert">{t("elearning.academy.builderData.selectionError")}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>{t("elearning.retry")}</button></>}
      {data && !items.length && <p>{t("elearning.academy.builderData.selectionEmpty")}</p>}
      {!plan && !instructor && items.length > 0 && <button type="button" onClick={() => update({ courseIds: items.map(item => item.id) })}>{t("elearning.academy.builderData.selectAllCourses")}</button>}
      {items.map(item => <label className="inspector-toggle-row academy-content-choice" key={item.id}><input type="checkbox" checked={(config[key] || []).includes(item.id)} onChange={event => update({ [key]: event.target.checked ? [...(config[key] || []), item.id] : (config[key] || []).filter(id => id !== item.id) })} /><span>{item.name}</span></label>)}
    </fieldset>}
  </fieldset>;
}
