import LearningErrorNotice from "../ELearning/LearningErrorNotice";
import LearningSettingsAccordion from "../ELearning/LearningSettingsAccordion";
import AcademyProgrammeSettings from "../ELearning/AcademyProgrammeSettings";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Save, Settings2, BookOpen, ListOrdered, Award, Info, Gift, Building2 } from "lucide-react";
import { elearningTerminologyGroups } from "../../config/elearningTerminology";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import ELearningDescriptionTextarea from "../ELearning/ELearningDescriptionTextarea";
import ELearningSkeleton from "../ELearning/ELearningSkeleton";
import { fetchELearningSettings, saveELearningSettings } from "../../services/elearningSettings";
import "../../styles/admin/dashboard/elearning.css";


const sections = [
  ["general", [["platform_name", "text", 120], ["description", "textarea", 2000]]],
  ["terminology", []],
  ["structure", [["sequential_progression", "toggle"], ["allow_locked_content", "toggle"], ["track_learner_progress", "toggle"]]],
  ["assessments", [["assessments_enabled", "toggle"], ["default_passing_score", "number"], ["certificates_enabled", "toggle"]]],
];

const sectionTabs = {general:'general',terminology:'learning',structure:'learning',assessments:'learning'};

const sectionIcons = { general: Settings2, terminology: BookOpen, structure: ListOrdered, assessments: Award, academy: BookOpen };

function TerminologySettings({ settings, update, t }) {
  return <div className="elearning-terminology">
    {elearningTerminologyGroups.map(({ key: group, fields }) =>
      <fieldset key={group} className={`elearning-terminology-group ${group === "learningStructure" ? "is-content" : "is-participants"}`}>
        <legend>{t(`elearning.terminologyGroups.${group}`)}</legend>
        <div className="elearning-terminology-fields">
          {fields.map(({ key, options }) => {
            // Preserve older tenant labels until the admin explicitly replaces them.
            const legacyValue = !options.includes(settings[key]);
            return <div className="elearning-terminology-step" key={key}>
              <label className="elearning-field" htmlFor={`elearning-${key}`}>
                <span>{t(`elearning.fields.${key}`)}</span>
                <select id={`elearning-${key}`} value={settings[key]} required
                  aria-describedby={legacyValue ? `elearning-legacy-${key}` : undefined}
                  onChange={(event) => update(key, event.target.value)}>
                  {legacyValue && <option value={settings[key]} disabled>{settings[key]}</option>}
                  {options.map((option) => <option value={option} key={option}>{option}</option>)}
                </select>
              </label>
              {legacyValue && <small id={`elearning-legacy-${key}`}>{t("elearning.savedTerminologyHelp")}</small>}
            </div>;
          })}
        </div>
      </fieldset>
    )}
  </div>;
}

export default function ELearningSettingsPage({ user }) {
  const { t, i18n } = useTranslation("dashboard");
  const { updateSettings } = useELearningTerminology();
  const [capabilities, setCapabilities] = useState({});
  const [settings, setSettings] = useState(null);
  const [referralsAvailable, setReferralsAvailable] = useState(false);
  const [available, setAvailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [activeTab, setActiveTab] = useState(() => new URLSearchParams(window.location.search).get("tab") || "general");
  const [requestedSection] = useState(() => new URLSearchParams(window.location.search).get("section"));
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchELearningSettings().then((data) => {
      if (!cancelled) { setCapabilities(data.capabilities || {}); setSettings(data.settings); setAvailable(data.available); setReferralsAvailable(Boolean(data.referrals_available)); }
    }).catch((failure) => {
      if (!cancelled) setError(failure.status === 403 ? "forbidden" : "loadError");
    }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [user?.tenant_id, user?.id, reload]);

  const update = (key, value) => {
    setSettings((current) => ({ ...current, ...(key === "academy_enabled" && value ? { enabled: true } : {}), [key]: value }));
    setSaved(false);
    setError("");
  };
  const save = async (event) => {
    event.preventDefault();
    if (!available) { setError("upgradeRequired"); return; }
    setSaving(true); setError(""); setSaved(false);
    try {
      const data = await saveELearningSettings(settings);
      setSettings(data.settings); updateSettings(data.settings); setSaved(true);
    } catch (failure) {
      setError(failure.status === 403 ? "forbidden" : [400, 422].includes(failure.status) ? "validationError" : "saveError");
    } finally { setSaving(false); }
  };


  const tabs=['general','learning',...(['referrals','affiliate','tuition','exchange','withdrawal'].some(key=>capabilities[key])?['programmes']:[]),'institution'];
  const currentTab=tabs.includes(activeTab)?activeTab:'general';
  function selectTab(event) {
    if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    event.preventDefault();
    const direction=i18n.dir()==='rtl'?-1:1;
    const index=tabs.indexOf(currentTab);
    const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?direction:-direction)+tabs.length)%tabs.length;
    setActiveTab(tabs[next]);event.currentTarget.parentElement.querySelectorAll('[role="tab"]')[next].focus();
  }
  function revealInvalidField(event) {
    const input=event.target;
    const panel=input.closest('[data-settings-tab]');
    const closed=[];
    for(let parent=input.parentElement;parent && parent!==event.currentTarget;parent=parent.parentElement) {
      if(parent.tagName==='DETAILS' && !parent.open)closed.push(parent);
    }
    if(!panel?.hidden && !closed.length)return;
    event.preventDefault();
    const first=event.currentTarget.querySelector('input:invalid,select:invalid,textarea:invalid');
    if(input!==first)return;
    if(panel)setActiveTab(panel.dataset.settingsTab);
    for(const section of closed)section.open=true;
    requestAnimationFrame(()=>{if(input.isConnected){input.focus();input.reportValidity();}});
  }
  function renderSections(tab) {
    return sections.filter(([section])=>sectionTabs[section]===tab).map(([section, fields]) => {
          const Icon = sectionIcons[section];
          const title=t(section === "structure" ? "elearning.structureSettings" : `elearning.${section}`);
          const description=t(`elearning.${section}Help`);
          const content=
          <div className="settings-form-grid">
            {section === "terminology" && <TerminologySettings settings={settings} update={update} t={t} />}
            {fields.map(([key, type, maxLength]) => <label key={key} className={type === "toggle" ? "elearning-toggle" : `elearning-field${section !== "terminology" ? " settings-wide-field" : ""}`}>
              <span className="elearning-field-copy"><span>{t(`elearning.fields.${key}`)}</span>
                {type === "toggle" && <small id={`elearning-help-${key}`}>{t(`elearning.hints.${key}`)}</small>}
              </span>
              {type === "textarea" ? <><ELearningDescriptionTextarea value={settings[key]} maxLength={maxLength} onChange={(event) => update(key, event.target.value)}
                placeholder={t("elearning.descriptionPlaceholder")} label={t(`elearning.fields.${key}`)} /></> :
                <input type={type === "toggle" ? "checkbox" : type} role={type === "toggle" ? "switch" : undefined}
                  aria-label={type === "toggle" ? t(`elearning.fields.${key}`) : undefined}
                  aria-describedby={type === "toggle" ? `elearning-help-${key}` : undefined}
                  checked={type === "toggle" ? settings[key] : undefined} value={type === "toggle" ? undefined : settings[key]}
                  required={type === "number" || (type === "text" && key !== "primary_display_name" && !key.startsWith("academy_"))}
                  min={type === "number" ? 0 : undefined} max={type === "number" ? 100 : undefined} step={type === "number" ? 1 : undefined}
                  maxLength={maxLength} onChange={(event) => update(key, type === "toggle" ? event.target.checked : type === "number" ? (event.target.value === "" ? "" : Number(event.target.value)) : event.target.value)} />}
            </label>)}
          </div>
        ;
          return tab==='learning' ? <LearningSettingsAccordion key={section} title={title} description={description} icon={Icon} group="elearning-learning-settings" defaultOpen={section==='terminology'}>{content}</LearningSettingsAccordion>
            : <section className="settings-card" key={section} aria-labelledby={`elearning-${section}`}>
              <header className="elearning-card-heading"><span className="elearning-card-icon"><Icon size={20} aria-hidden="true" /></span><div><h3 id={`elearning-${section}`}>{title}</h3><p>{description}</p></div></header>{content}
            </section>;
        });

  }

  if (loading) return <ELearningSkeleton variant="settings" label={t("elearning.loading")} lang={i18n.language} direction={i18n.dir()} />;
  return <main className="settings-page elearning-settings" dir={i18n.dir()}>
    <header className="settings-header app-page-intro">
      <div><h1 id="elearning-settings-title">{t("elearning.settings")}</h1><span>{t("elearning.settings_nav.help")}</span></div>
      {settings && <div className="elearning-settings-header-actions"><button className="settings-save-button" type="submit" form="elearning-settings-panel" disabled={saving || !available}><Save size={16} aria-hidden="true" />{t(saving ? "elearning.saving" : "elearning.save")}</button></div>}
    </header>
    {error && <LearningErrorNotice as="div" className="elearning-feedback is-error">{t(`elearning.${error}`)}{!settings && <button type="button" onClick={() => { setError(""); setLoading(true); setReload((value) => value + 1); }}>{t("elearning.retry")}</button>}</LearningErrorNotice>}
    {!loading && settings && <form onSubmit={save} onInvalidCapture={revealInvalidField} id="elearning-settings-panel" aria-labelledby="elearning-settings-title">
      {!available && <div className="elearning-notice" role="status"><Info size={20} aria-hidden="true" /><p>{t("elearning.upgradeRequired")}</p></div>}
      <fieldset disabled={saving} className="elearning-form">
        <nav className="elearning-settings-tabs" role="tablist" aria-label={t("elearning.settings_nav.sections")}>
          {tabs.map(tab=><button type="button" role="tab" id={`elearning-tab-${tab}`} aria-controls={`elearning-panel-${tab}`} aria-selected={currentTab===tab} tabIndex={currentTab===tab?0:-1} onClick={()=>setActiveTab(tab)} onKeyDown={selectTab} key={tab}>{t(`elearning.settings_nav.${tab}`)}</button>)}
        </nav>
        {tabs.map(tab=><div className="elearning-settings-tab-panel" role="tabpanel" id={`elearning-panel-${tab}`} aria-labelledby={`elearning-tab-${tab}`} data-settings-tab={tab} hidden={currentTab!==tab} key={tab}>
          {renderSections(tab)}
          {tab==='general' && <AcademyProgrammeSettings settings={settings} capabilities={capabilities} visibleGroups={['notifications']} update={update} />}
          {tab==='programmes' && <>
        {capabilities.referrals && <LearningSettingsAccordion title={t("elearning.referrals.settings")} description={t("elearning.referrals.settingsHelp")} icon={Gift} group="elearning-programme-settings" defaultOpen={requestedSection === "referrals" || (!requestedSection && !capabilities.affiliate && !capabilities.tuition && !capabilities.exchange)}>
          {!referralsAvailable && <p role="status">{t("elearning.referrals.upgradeRequired")}</p>}
          <fieldset disabled={!referralsAvailable} className="settings-form-grid">
            <label className="elearning-toggle"><span>{t("elearning.referrals.enable")}</span><input type="checkbox" role="switch" checked={Boolean(settings.referral_rewards_enabled)} onChange={event => update("referral_rewards_enabled", event.target.checked)} /></label>
            <label className="elearning-field"><span>{t("elearning.referrals.amount")}</span><input type="number" min={settings.referral_rewards_enabled ? "0.01" : "0"} max="999999999999.99" step="0.01" required value={settings.referral_reward_amount ?? "0.00"} onChange={event => update("referral_reward_amount", event.target.value)} /></label>
            <label className="elearning-field"><span>{t("elearning.referrals.currency")}</span>
              <select required value={settings.referral_reward_currency || "USD"} onChange={event => update("referral_reward_currency", event.target.value)}>
                {["USD", "ILS", "EUR"].map(currency => <option key={currency} value={currency}>{t(`elearning.referrals.currencies.${currency}`)}</option>)}
                {settings.referral_reward_currency && !["USD", "ILS", "EUR"].includes(settings.referral_reward_currency) && <option value={settings.referral_reward_currency}>{settings.referral_reward_currency}</option>}
              </select>
            </label>
            <label className="elearning-toggle"><span>{t("elearning.adminControls.reviewRequired")}</span><input type="checkbox" role="switch" checked={Boolean(settings.referral_reward_review_required)} onChange={event => update("referral_reward_review_required", event.target.checked)} /></label>
            <label className="elearning-field">{t("elearning.programmes.referral_eligibility")}<select value={settings.referral_eligibility || "registration"} onChange={e=>update("referral_eligibility",e.target.value)}>{["registration","purchase_or_affiliate"].map(value=><option key={value} value={value}>{t(`elearning.programmes.${value}`)}</option>)}</select></label><p>{t("elearning.referrals.termsHelp")}</p>
          </fieldset>
        </LearningSettingsAccordion>}

          <AcademyProgrammeSettings settings={settings} capabilities={capabilities} visibleGroups={['commerce_settings','affiliate_settings','support_settings','exchange_settings','withdrawal_settings']} compact expandedGroup={requestedSection} update={update} />
          </>}
          {tab==='institution' && <>
        <section className="settings-card elearning-institution-card" aria-labelledby="elearning-institution-title">
          <header className="elearning-card-heading">
            <span className="elearning-card-icon"><Building2 size={20} aria-hidden="true" /></span>
            <div><h3 id="elearning-institution-title">{t("elearning.owner.institution")}</h3><p>{t("elearning.settings_nav.institution_help")}</p></div>
          </header>
          <label className="elearning-toggle"><span>{t("elearning.owner.institution_enabled")}</span><input type="checkbox" role="switch" checked={Boolean(settings.institution_enabled)} onChange={event => update("institution_enabled", event.target.checked)} /></label>
          <fieldset className="elearning-institution-group">
            <legend>{t("elearning.settings_nav.institution_details")}</legend>
            <div className="elearning-institution-fields">
              <label className="elearning-field">{t("elearning.owner.institution_name")}<input maxLength={160} required={settings.institution_enabled} value={settings.institution_name ?? ""} onChange={event => update("institution_name", event.target.value)} /></label>
              <label className="elearning-field">{t("elearning.owner.institution_domains")}<textarea required={settings.institution_enabled} aria-label={t("elearning.owner.institution_domains")} aria-describedby="elearning-institution-domain-help" value={(settings.institution_email_domains || []).join("\n")} onChange={event => update("institution_email_domains", event.target.value.split(/[\n,]/).map(value => value.trim()).filter(Boolean))} /><small id="elearning-institution-domain-help">{t("elearning.settings_nav.institution_domain_help")}</small></label>
            </div>
          </fieldset>
          <fieldset className="elearning-institution-group">
            <legend>{t("elearning.settings_nav.student_labels")}</legend>
            <div className="elearning-institution-fields">{["institution_student_label", "regular_student_label"].map(key => <label className="elearning-field" key={key}>{t(`elearning.owner.${key}`)}<input maxLength={120} required={settings.institution_enabled} value={settings[key] ?? ""} onChange={event => update(key, event.target.value)} /></label>)}</div>
          </fieldset>
        </section>

          </>}
        </div>)}
      </fieldset>
      {saved && <p role="status" className="elearning-feedback">{t("elearning.saved")}</p>}
    </form>}
  </main>;
}
