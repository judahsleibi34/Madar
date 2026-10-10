import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Save, Settings2, BookOpen, ListOrdered, Award, Palette, Info, Upload, Gift } from "lucide-react";
import { elearningTerminologyGroups } from "../../config/elearningTerminology";
import { resolveMediaUrl } from "../../utils/media";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import ELearningDescriptionTextarea from "../ELearning/ELearningDescriptionTextarea";
import ELearningSkeleton from "../ELearning/ELearningSkeleton";
import { fetchELearningSettings, saveELearningSettings, uploadELearningLogo } from "../../services/elearningSettings";
import "../../styles/admin/dashboard/elearning.css";


const sections = [
  ["general", [["platform_name", "text", 120], ["description", "textarea", 2000]]],
  ["terminology", []],
  ["structure", [["sequential_progression", "toggle"], ["allow_locked_content", "toggle"], ["track_learner_progress", "toggle"]]],
  ["assessments", [["assessments_enabled", "toggle"], ["default_passing_score", "number"], ["certificates_enabled", "toggle"]]],
  ["appearance", [["primary_display_name", "text", 120], ["logo_url", "url", 2048]]],
];

const sectionIcons = { general: Settings2, terminology: BookOpen, structure: ListOrdered, assessments: Award, appearance: Palette, academy: BookOpen };

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
  const [settings, setSettings] = useState(null);
  const [referralsAvailable, setReferralsAvailable] = useState(false);
  const [available, setAvailable] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchELearningSettings().then((data) => {
      if (!cancelled) { setSettings(data.settings); setAvailable(data.available); setReferralsAvailable(Boolean(data.referrals_available)); }
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
  const uploadLogo = async (event, key = "logo_url") => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setUploadError("");
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || !file.size || file.size > 5 * 1024 * 1024) {
      setUploadError("imageUploadInvalid");
      return;
    }
    setUploading(true);
    try {
      const data = await uploadELearningLogo(file);
      update(key, data.asset_url);
    } catch (failure) {
      setUploadError(failure.status === 403 ? "imageUploadForbidden" : [400, 413, 422].includes(failure.status) ? "imageUploadInvalid" : "imageUploadError");
    } finally { setUploading(false); }
  };
  const save = async (event) => {
    event.preventDefault();
    if (uploading) return;
    if (!available) { setError("upgradeRequired"); return; }
    setSaving(true); setError(""); setSaved(false);
    try {
      const data = await saveELearningSettings(settings);
      setSettings(data.settings); updateSettings(data.settings); setSaved(true);
    } catch (failure) {
      setError(failure.status === 403 ? "forbidden" : [400, 422].includes(failure.status) ? "validationError" : "saveError");
    } finally { setSaving(false); }
  };

  if (loading) return <ELearningSkeleton variant="settings" label={t("elearning.loading")} lang={i18n.language} direction={i18n.dir()} />;
  return <main className="settings-page elearning-settings" dir={i18n.dir()}>
    <header className="settings-header app-page-intro">
      <div><h1 id="elearning-settings-title">{t("elearning.settings")}</h1><span>{t("elearning.subtitle")}</span></div>
    </header>
    {error && <div role="alert" className="elearning-feedback is-error">{t(`elearning.${error}`)}{!settings && <button type="button" onClick={() => { setError(""); setLoading(true); setReload((value) => value + 1); }}>{t("elearning.retry")}</button>}</div>}
    {!loading && settings && <form onSubmit={save} id="elearning-settings-panel" aria-labelledby="elearning-settings-title">
      {!available && <div className="elearning-notice" role="status"><Info size={20} aria-hidden="true" /><p>{t("elearning.upgradeRequired")}</p></div>}
      <fieldset disabled={saving || uploading} className="elearning-form">
        {sections.map(([section, fields]) => {
          const Icon = sectionIcons[section];
          return <section className={`settings-card${section === "appearance" ? " elearning-branding-card" : ""}`} key={section} aria-labelledby={`elearning-${section}`}>
          <header className="elearning-card-heading">
            <span className="elearning-card-icon"><Icon size={20} aria-hidden="true" /></span>
            <div><h3 id={`elearning-${section}`}>{t(section === "academy" ? "elearning.academy.settings" : section === "structure" ? "elearning.structureSettings" : `elearning.${section}`)}</h3>
            <p>{t(section === "academy" ? "elearning.academy.settingsHelp" : `elearning.${section}Help`)}</p></div>
          </header>
          <div className="settings-form-grid">
            {section === "terminology" && <TerminologySettings settings={settings} update={update} t={t} />}
            {fields.map(([key, type, maxLength]) => ["logo_url", "academy_hero_image"].includes(key) ? <div key={key} className="elearning-logo-field settings-wide-field">
              <label htmlFor={`elearning-${key}-url`}><span>{t(`elearning.fields.${key}`)}</span>
                <input id={`elearning-${key}-url`} type="text" value={settings[key]} maxLength={maxLength}
                  onChange={(event) => update(key, event.target.value)} />
              </label>
              <div className="elearning-logo-upload">
                {settings[key] && <img className="elearning-logo-preview" src={resolveMediaUrl(settings[key])} alt={t("elearning.logoPreview")} />}
                <div><label className="elearning-upload-button" htmlFor={`elearning-${key}-file`}><Upload size={16} aria-hidden="true" /><span>{t("elearning.uploadImage")}</span></label>
                  <input id={`elearning-${key}-file`} className="elearning-file-input" type="file" accept="image/png,image/jpeg,image/webp"
                    aria-label={t("elearning.uploadImage")} aria-describedby="elearning-upload-help" disabled={saving || uploading || !available} onChange={event => uploadLogo(event, key)} />
                </div>
              </div>
              <small id="elearning-upload-help">{t("elearning.imageUploadHelp")}</small>
              {uploading && <p role="status">{t("elearning.uploadingImage")}</p>}
              {uploadError && <p role="alert" className="elearning-feedback is-error">{t(`elearning.${uploadError}`)}</p>}
            </div> : <label key={key} className={type === "toggle" ? "elearning-toggle" : `elearning-field${section !== "terminology" ? " settings-wide-field" : ""}`}>
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
        </section>; })}
        <section className="settings-card" aria-labelledby="elearning-referrals">
          <header className="elearning-card-heading"><span className="elearning-card-icon"><Gift size={20} aria-hidden="true" /></span><div><h3 id="elearning-referrals">{t("elearning.referrals.settings")}</h3><p>{t("elearning.referrals.settingsHelp")}</p></div></header>
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
            <p>{t("elearning.referrals.termsHelp")}</p>
          </fieldset>
        </section>
        <div className="elearning-actions"><button className="settings-save-button" type="submit" disabled={saving || uploading || !available}><Save size={16} aria-hidden="true" />{t(saving ? "elearning.saving" : "elearning.save")}</button></div>
      </fieldset>
      {saved && <p role="status" className="elearning-feedback">{t("elearning.saved")}</p>}
    </form>}
  </main>;
}
