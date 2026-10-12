import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ExternalLink, Image, Monitor, RotateCcw, Save, Smartphone, Upload } from "lucide-react";
import { fetchELearningSettings, saveELearningSettings, uploadELearningLogo } from "../../services/elearningSettings";
import { initializeAcademyLanding } from "../../services/elearningAcademy";
import { fetchBuilderProject, updateBuilderProject, publishBuilderProject } from "../PageBuilder/services/PageBuilder.api";
import { validateBuilderSaveAcknowledgement, validateBuilderSchemaAcknowledgement } from "../PageBuilder/core/PageBuilder.persistence";
import { defaultTheme, themePresets } from "../PageBuilder/core/PageBuilder.constants";
import { getPageBuilderThemeVars, pageBuilderFontFamilyOptions } from "../PageBuilder/core/PageBuilder.theme";
import { useELearningTerminology } from "../../hooks/useELearningTerminology";
import { resolveMediaUrl } from "../../utils/media";
import ELearningSkeleton from "./ELearningSkeleton";
import "../../styles/admin/dashboard/elearning.css";
import "../../styles/academy-theme.css";

const colors = ["accent", "background", "surface", "text", "muted"];
const additionalColors = ["headerBackground", "softSurface", "accentDark", "buttonText"];
const isHexColor = value => /^#[0-9a-f]{6}$/i.test(String(value || ""));

export default function AcademyThemePage({ user }) {
  const { t, i18n } = useTranslation("dashboard");
  const { updateSettings } = useELearningTerminology();
  const [state, setState] = useState({ loading: true });
  const [draft, setDraft] = useState(null);
  const [branding, setBranding] = useState(null);
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [notice, setNotice] = useState(null);
  const [attempt, setAttempt] = useState(0);
  const [previewMode, setPreviewMode] = useState("desktop");

  function acceptRecord(record) {
    if (!record?.id || record.usage_profile !== "academy" || !Array.isArray(record.draft_schema?.pages) || !Number.isInteger(record.draft_revision)) {
      throw new Error("Invalid Academy project");
    }
    return record;
  }

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const data = await fetchELearningSettings();
        const id = data.academy_management?.editor_project_id || data.academy_management?.landing_project?.id;
        const record = id ? acceptRecord(await fetchBuilderProject(id)) : null;
        if (!active) return;
        setState({ data, record });
        setBranding(data.settings);
        setDraft(record?.draft_schema || null);
        setDirty(false);
      } catch (error) {
        if (active) setState({ error: error.status === 403 ? "elearning.forbidden" : "elearning.loadError" });
      }
    }
    load();
    return () => { active = false; };
  }, [user?.tenant_id, user?.id, attempt]);

  function editTheme(key, value) {
    setDraft(current => ({ ...current, theme: { ...current.theme, [key]: value } }));
    setDirty(true); setNotice(null);
  }
  function editBrand(key, value) {
    setBranding(current => ({ ...current, [key]: value }));
    setDirty(true); setNotice(null);
  }
  async function createHome() {
    setBusy(true); setNotice(null);
    try {
      const record = acceptRecord(await initializeAcademyLanding());
      setState(current => ({ ...current, record })); setDraft(record.draft_schema);
    } catch { setNotice({ error: true, key: "elearning.academy.editorOpenError" }); }
    finally { setBusy(false); }
  }
  async function upload(event) {
    const file = event.target.files?.[0]; event.target.value = "";
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type) || !file.size || file.size > 5 * 1024 * 1024) {
      setNotice({ error: true, key: "elearning.imageUploadInvalid" }); return;
    }
    setBusy(true); setNotice(null);
    try { const asset = await uploadELearningLogo(file); editBrand("logo_url", asset.asset_url); }
    catch { setNotice({ error: true, key: "elearning.imageUploadError" }); }
    finally { setBusy(false); }
  }
  async function save(event) {
    event.preventDefault();
    if (busy || !state.data.available || !state.record || notice?.conflict) return;
    if (!colorsValid) { setNotice({ error: true, key: "elearning.theme.invalidColors" }); return; }
    setBusy(true); setNotice(null);
    let draftSaved = false;
    try {
      const brand = branding.primary_display_name || branding.platform_name;
      const nextDraft = { ...draft, siteChrome: { ...draft.siteChrome, logoUrl: branding.logo_url, brand, footerStoreName: brand } };
      const record = await updateBuilderProject(state.record.id, {
        draft_schema: nextDraft, expected_revision: state.record.draft_revision,
      });
      validateBuilderSaveAcknowledgement({ projectId: state.record.id, previousRevision: state.record.draft_revision, savedRecord: record });
      validateBuilderSchemaAcknowledgement({ savedRecord: record, submittedProject: nextDraft });
      acceptRecord(record);
      setState(current => ({ ...current, record })); setDraft(record.draft_schema);
      draftSaved = true;
      const result = await saveELearningSettings(branding);
      setBranding(result.settings); updateSettings(result.settings);
      setDirty(false); setNotice({ key: "elearning.theme.saved" });
    } catch (error) {
      setNotice({ error: true, conflict: error.status === 409, key: error.status === 409 ? "elearning.theme.conflict" : draftSaved ? "elearning.theme.brandSaveError" : "elearning.saveError" });
    } finally { setBusy(false); }
  }
  async function publish() {
    if (busy || dirty || notice?.conflict || notice?.key === "elearning.theme.brandSaveError" || !state.data.available) return;
    setBusy(true); setNotice(null);
    try {
      await publishBuilderProject(state.record.id, state.record.draft_revision);
      setNotice({ key: "elearning.theme.published" });
    } catch (error) {
      setNotice({ error: true, conflict: error.status === 409, key: error.status === 409 ? "elearning.theme.conflict" : "elearning.theme.publishError" });
    } finally { setBusy(false); }
  }
  function reload() { setState({ loading: true }); setNotice(null); setAttempt(value => value + 1); }

  if (state.loading) return <ELearningSkeleton variant="settings" label={t("elearning.loading")} direction={i18n.dir()} lang={i18n.language} />;
  if (state.error) return <main className="settings-page" dir={i18n.dir()}><p role="alert">{t(state.error)}</p><button onClick={reload}>{t("elearning.retry")}</button></main>;
  const theme = { ...defaultTheme, ...draft?.theme };
  const colorsValid = [...colors, ...additionalColors].every(key => (key === "headerBackground" && !theme[key]) || isHexColor(theme[key]));
  const previewTheme = { ...theme };
  [...colors, ...additionalColors].forEach(key => {
    if (!isHexColor(previewTheme[key])) previewTheme[key] = key === "headerBackground" ? (isHexColor(theme.surface) ? theme.surface : defaultTheme.surface) : defaultTheme[key];
  });
  const logo = resolveMediaUrl(branding.logo_url);
  const colorRow = key => {
    const value = key === "headerBackground" && !theme[key] ? previewTheme.headerBackground : theme[key];
    return <div className="ecommerce-theme-color-row" key={key}>
      <input type="color" value={previewTheme[key]} aria-label={`${t(`elearning.theme.tokens.${key}`)} ${t("elearning.theme.colorPicker")}`} onChange={event => editTheme(key, event.target.value)} />
      <span><strong>{t(`elearning.theme.tokens.${key}`)}</strong><small>{t(`elearning.theme.tokenHelp.${key}`)}</small></span>
      <input type="text" dir="ltr" value={value} maxLength={7} spellCheck={false} aria-label={t(`elearning.theme.tokens.${key}`)} aria-invalid={!isHexColor(value)} className={!isHexColor(value) ? "is-invalid" : ""} onChange={event => editTheme(key, event.target.value)} />
    </div>;
  };
  return <main className="ecommerce-theme-page academy-theme-page" dir={i18n.dir()} lang={i18n.language}>
    <header className="ecommerce-page-header app-page-intro"><div><h1>{t("elearning.theme.designTitle")}</h1><p>{t("elearning.theme.designIntro")}</p></div></header>
    {notice && <p className={`elearning-feedback${notice.error ? " is-error" : ""}`} role={notice.error ? "alert" : "status"}>{t(notice.key)}{notice.conflict && <button type="button" onClick={reload}>{t("elearning.theme.reload")}</button>}</p>}
    {!state.record ? <section className="ecommerce-theme-controls"><p>{t("elearning.theme.createHelp")}</p><button className="ecommerce-primary-button" disabled={busy || !state.data.available} onClick={createHome}>{t("elearning.theme.createHome")}</button></section> : <form onSubmit={save} aria-label={t("elearning.theme.title")}>
      {!state.data.available && <p role="status">{t("elearning.upgradeRequired")}</p>}
      <div className="ecommerce-theme-layout">
        <fieldset disabled={busy || !state.data.available || notice?.conflict} className="ecommerce-theme-controls academy-theme-controls">
          <section className="academy-theme-branding" aria-labelledby="academy-branding-title">
            <h2 id="academy-branding-title" className="ecommerce-theme-section-title">{t("elearning.theme.logoTitle")}</h2>
            <div className="academy-theme-logo-row">
              <div className="academy-theme-logo-tile">{logo ? <img src={logo} alt={t("elearning.logoPreview")} /> : <Image size={28} aria-hidden="true" />}</div>
              <div className="academy-theme-logo-actions">
                <label className="ecommerce-secondary-button academy-theme-upload" htmlFor="academy-theme-logo"><Upload size={16} aria-hidden="true" />{t("elearning.uploadImage")}</label>
                <input id="academy-theme-logo" className="elearning-file-input" type="file" accept="image/png,image/jpeg,image/webp" aria-label={t("elearning.uploadImage")} onChange={upload} />
                {branding.logo_url && <button type="button" className="academy-theme-remove" onClick={() => editBrand("logo_url", "")}>{t("elearning.theme.removeLogo")}</button>}
                <small>{t("elearning.theme.uploadHelp")}</small>
              </div>
            </div>
            <label className="academy-theme-field"><span>{t("elearning.fields.primary_display_name")}</span><input maxLength={120} placeholder={branding.platform_name} value={branding.primary_display_name || ""} onChange={event => editBrand("primary_display_name", event.target.value)} /></label>
          </section>
          <section aria-labelledby="academy-colors-title">
            <h2 id="academy-colors-title" className="ecommerce-theme-section-title">{t("elearning.theme.colors")}</h2>
            <div className="ecommerce-theme-color-list">{colors.map(colorRow)}</div>
            <button type="button" className="ecommerce-theme-reset" onClick={() => { setDraft(current => ({ ...current, theme: { ...state.record.draft_schema.theme } })); setDirty(true); setNotice(null); }}><RotateCcw size={16} aria-hidden="true" />{t("elearning.theme.restoreColors")}</button>
            <details className="academy-theme-advanced"><summary>{t("elearning.theme.moreOptions")}</summary>
              <div className="academy-theme-presets">{Object.entries(themePresets).map(([key, preset]) => <button type="button" key={key} className="ecommerce-secondary-button" onClick={() => { setDraft(current => ({ ...current, theme: { ...current.theme, ...preset } })); setDirty(true); setNotice(null); }}>{t(`elearning.theme.${key}`)}</button>)}</div>
              <div className="ecommerce-theme-color-list">{additionalColors.map(colorRow)}</div>
              <div className="academy-theme-typography"><label className="academy-theme-field"><span>{t("elearning.theme.font")}</span><select value={theme.fontFamily} onChange={event => editTheme("fontFamily", event.target.value)}>{pageBuilderFontFamilyOptions.map(font => <option key={font}>{font}</option>)}</select></label>
                <label className="academy-theme-field"><span>{t("elearning.theme.radius")}</span><input type="number" min={0} max={100} required value={theme.radius} onChange={event => editTheme("radius", event.target.value === "" ? "" : Number(event.target.value))} /></label></div>
            </details>
          </section>
          {!colorsValid && <p className="elearning-feedback is-error" role="alert">{t("elearning.theme.invalidColors")}</p>}
          <footer className="ecommerce-theme-settings-footer academy-theme-footer"><button className="ecommerce-primary-button" type="submit" disabled={!dirty || !colorsValid}><Save size={16} aria-hidden="true" />{t(busy ? "elearning.saving" : "elearning.theme.saveDraft")}</button><button type="button" className="ecommerce-secondary-button" disabled={dirty || notice?.conflict || notice?.key === "elearning.theme.brandSaveError"} onClick={publish}>{t("elearning.theme.publish")}</button></footer>
          <p className="academy-theme-publish-help">{t("elearning.theme.publishHelp")}</p>
        </fieldset>
        <aside className="ecommerce-theme-preview" aria-label={t("elearning.theme.preview")}>
          <div className="ecommerce-theme-preview-label"><span>{t("elearning.theme.preview")}</span><small>{t("elearning.theme.previewUpdates")}</small></div>
          <div className="ecommerce-theme-preview-toolbar">
            <div className="ecommerce-theme-device-controls" role="group" aria-label={t("elearning.theme.previewDevice")}>
              <button type="button" aria-pressed={previewMode === "desktop"} onClick={() => setPreviewMode("desktop")}><Monitor size={16} aria-hidden="true" />{t("elearning.theme.desktop")}</button>
              <button type="button" aria-pressed={previewMode === "mobile"} onClick={() => setPreviewMode("mobile")}><Smartphone size={16} aria-hidden="true" />{t("elearning.theme.mobile")}</button>
            </div>
            <Link className="ecommerce-secondary-button" to={`/e-learning/landing-page/projects/${encodeURIComponent(state.record.id)}/preview`} target="_blank" rel="noopener noreferrer"><ExternalLink size={16} aria-hidden="true" />{t("elearning.theme.openSavedPreview")}</Link>
          </div>
          <div className="academy-theme-preview-shell">
            <div className={`academy-theme-sample is-${previewMode}`} style={getPageBuilderThemeVars(previewTheme)}>
              <header>{logo && <img src={logo} alt="" />}<strong>{branding.primary_display_name || branding.platform_name}</strong><span>{t("elearning.academy.courses")}</span></header>
              <section><small>{t("elearning.theme.previewEyebrow")}</small><h3>{t("elearning.theme.previewHeading")}</h3><p>{t("elearning.theme.previewText")}</p><span className="academy-theme-preview-button">{t("elearning.academy.explore")}</span></section>
              <div className="academy-theme-preview-card"><strong>{t("elearning.academy.courses")}</strong><p>{t("elearning.theme.previewCard")}</p><div className="academy-theme-course-swatches"><i /><i /><i /></div></div>
              <footer><strong>{branding.primary_display_name || branding.platform_name}</strong><span>{t("elearning.theme.previewFooter")}</span></footer>
            </div>
          </div>
        </aside>
      </div>
    </form>}
  </main>;
}
