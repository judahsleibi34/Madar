import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { GraduationCap, LayoutTemplate, BookOpen, Globe, Settings2, CreditCard } from "lucide-react";
import { fetchELearningSettings, saveELearningSettings } from "../../services/elearningSettings";
import { initializeAcademyLanding } from "../../services/elearningAcademy";
import { getBuilderPublicationState } from "../PageBuilder/core/PageBuilder.publishState";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import { academyPath } from "./AcademyNav";
import ELearningSkeleton from "./ELearningSkeleton";
import "../../styles/academy-management-hub.css";

export default function AcademyManagementHub({ user }) {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation("dashboard");
  const { updateSettings } = useELearningTerminology();
  const [state, setState] = useState({ loading: true });
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  useEffect(() => {
    let active = true;
    fetchELearningSettings().then(data => { if (active) setState({ data, domainsText: (data.settings.academy_email_domains || []).join(", ") }); }).catch(() => { if (active) setState({ error: true }); });
    return () => { active = false; };
  }, [user?.id, user?.tenant_id, attempt]);
  if (state.loading) return <ELearningSkeleton variant="settings" label={t("elearning.loading")} direction={i18n.dir()} lang={i18n.language} />;
  if (state.error) return <main className="ecommerce-page" dir={i18n.dir()}><p role="alert">{t("elearning.loadError")}</p><button className="ecommerce-secondary-button" onClick={() => { setState({ loading: true }); setAttempt(value => value + 1); }}>{t("elearning.retry")}</button></main>;
  const { settings, academy_management: management, available } = state.data;
  const project = management?.landing_project;
  const publication = getBuilderPublicationState(project);
  const publicPath = management?.subdomain ? academyPath(management) : state.data.academy ? academyPath(state.data.academy) : null;
  const enabled = settings.enabled && settings.academy_enabled;
  const published = project?.published_schema && management?.published_project_id === project.id;
  const status = !enabled ? "disabled" : published ? "published" : "draft";
  async function edit() {
    setBusy(true); setNotice(null);
    try {
      const landing = await initializeAcademyLanding();
      navigate(`/e-learning/landing-page/projects/${landing.id}/pages`);
    } catch (error) {
      const key = !error.status ? "editorNetworkError" : error.status === 402 ? "editorPlanError" : error.status === 403 ? "editorPermissionError" : error.status === 404 || error.code === "academy_project_missing" ? "editorMissingError" : error.status === 400 || error.status === 422 ? "editorValidationError" : error.code === "academy_builder_upgrade_required" ? "editorUpgradeError" : "editorOpenError";
      setNotice({ error: true, key: `elearning.academy.${key}` }); setBusy(false);
    }
  }
  async function save(event) {
    event.preventDefault(); setBusy(true); setNotice(null);
    const domains = (state.domainsText || "").split(/[,\n]/).map(value => value.trim()).filter(Boolean);
    if (settings.academy_registration === "email_domain" && !domains.length) {
      setNotice({ error: true, key: "elearning.learner.domainsRequired" }); setBusy(false); return;
    }
    try {
      const result = await saveELearningSettings({ ...settings, academy_email_domains: domains });
      updateSettings(result.settings);
      setState(current => ({ ...current, data: { ...current.data, ...result }, domainsText: (result.settings.academy_email_domains || []).join(", ") })); setNotice({ saved: true });
    } catch (error) { setNotice({ error: true, ...(error.status === 422 ? { key: "elearning.learner.domainsInvalid" } : {}) }); } finally { setBusy(false); }
  }
  return <main className="ecommerce-page academy-management-hub" dir={i18n.dir()} lang={i18n.language}>
    <header className="ecommerce-page-header app-page-intro"><div><h1>{t("elearning.academy.academyAccess")}</h1><p>{t("elearning.academy.hubIntro")}</p></div><span className={`elearning-course-status is-${status}`}><GraduationCap size={16} />{t(`elearning.academy.hubStatus.${status}`)}</span></header>
    {notice && <p role={notice.error ? "alert" : "status"}>{t(notice.error ? notice.key || "elearning.saveError" : "elearning.saved")}</p>}
    {notice?.key === "elearning.academy.editorPlanError" && <Link className="ecommerce-secondary-button" to="/my-plan">{t("elearning.academy.reviewPlan")}</Link>}
    <div className="academy-management-grid">
      <section className="ecommerce-list-card academy-management-card"><h2 className="academy-management-card-heading"><LayoutTemplate size={24} aria-hidden="true" /><span>{t("elearning.academy.landingPage")}</span></h2><p>{t("elearning.academy.landingHelp")}</p><small>{t(`elearning.academy.landingStatus.${publication.status}`)}</small><div className="elearning-course-actions"><button className="ecommerce-primary-button" disabled={busy || !available} onClick={() => edit()}>{t("elearning.academy.editAcademy")}</button><Link className="ecommerce-secondary-button" to="/my-learning" target="_blank" rel="noopener noreferrer">{t("elearning.academy.previewLanding")}</Link></div></section>
      <section className="ecommerce-list-card academy-management-card"><h2 className="academy-management-card-heading"><BookOpen size={24} aria-hidden="true" /><span>{t("elearning.academy.studentPlatform")}</span></h2><p>{t("elearning.academy.studentHelp")}</p><Link className="ecommerce-primary-button" to="/my-learning" target="_blank" rel="noopener noreferrer">{t("elearning.academy.openStudent")}</Link></section>
      <section className="ecommerce-list-card academy-management-card"><h2 className="academy-management-card-heading"><Globe size={24} aria-hidden="true" /><span>{t("elearning.academy.publicAcademy")}</span></h2><p>{t("elearning.academy.publicHelp")}</p>{publicPath ? <Link className="ecommerce-secondary-button" to={publicPath} target="_blank" rel="noopener noreferrer">{t("elearning.academy.open")}</Link> : <p>{t("elearning.academy.addressRequired")}</p>}</section>
      <section className="ecommerce-list-card academy-management-card"><h2 className="academy-management-card-heading"><CreditCard size={24} aria-hidden="true" /><span>{t("elearning.academy.learningPlans")}</span></h2><p>{t("elearning.academy.pricingHelp")}</p><Link className="ecommerce-secondary-button" to="/e-learning/plans">{t("elearning.academy.managePlans")}</Link></section>
    </div>
    <form className="ecommerce-list-card academy-management-access" onSubmit={save}>
      <header className="academy-access-header">
        <h2 className="academy-management-card-heading"><Settings2 size={24} aria-hidden="true" /><span>{t("elearning.academy.accessSettings")}</span></h2>
        <p>{t("elearning.academy.accessHelp")}</p>
      </header>
      <fieldset disabled={busy || !available}>
        <label className="academy-access-toggle">
          <span className="academy-access-setting-copy"><strong>{t("elearning.fields.academy_enabled")}</strong><small>{t("elearning.academy.enableHelp")}</small></span>
          <span className="academy-access-switch">
            <input type="checkbox" role="switch" aria-label={t("elearning.fields.academy_enabled")} checked={settings.academy_enabled} onChange={event => setState(current => ({ ...current, data: { ...current.data, settings: { ...settings, academy_enabled: event.target.checked, ...(event.target.checked ? { enabled: true } : {}) } } }))} />
            <span className="academy-access-switch-track" aria-hidden="true" />
          </span>
        </label>
        <div className="academy-access-registration">
          <label className="elearning-field" htmlFor="academy-registration">{t("elearning.learner.registrationPolicy")}</label>
          <select id="academy-registration" aria-describedby="academy-registration-help" value={settings.academy_registration || "invitation_only"} onChange={event => setState(current => ({ ...current, data: { ...current.data, settings: { ...settings, academy_registration: event.target.value } } }))}>
            <option value="invitation_only">{t("elearning.learner.invitationOnly")}</option>
            <option value="open">{t("elearning.learner.openRegistration")}</option>
            <option value="email_domain">{t("elearning.learner.emailDomainRegistration")}</option>
          </select>
          <p id="academy-registration-help">{t(`elearning.learner.registrationHelp.${settings.academy_registration || "invitation_only"}`)}</p>
        </div>
        {settings.academy_registration === "email_domain" && <label className="elearning-field academy-email-domains"><span>{t("elearning.learner.allowedEmailDomains")}</span><input aria-label={t("elearning.learner.allowedEmailDomains")} aria-describedby="academy-domain-help" required maxLength={5200} value={state.domainsText || ""} placeholder="jack@university.edu, college.edu" onChange={event => setState(current => ({ ...current, domainsText: event.target.value }))} /><small id="academy-domain-help">{t("elearning.learner.emailDomainHelp")}</small></label>}
        <footer className="academy-access-footer"><button className="ecommerce-primary-button" type="submit">{t(busy ? "elearning.saving" : "elearning.save")}</button></footer>
      </fieldset>
    </form>
  </main>;
}
