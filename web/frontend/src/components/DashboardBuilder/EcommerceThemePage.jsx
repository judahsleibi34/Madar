import { notifyCommerceAction } from "../../utils/commerceActionToast";
import { useEffect, useMemo, useRef, useState } from "react";
import { ExternalLink, LoaderCircle, Monitor, RotateCcw, Rocket, Smartphone } from "lucide-react";

import AuthToast from "../AuthPages/AuthToast";
import { fetchEcommerceTheme, saveEcommerceTheme } from "../../services/ecommerceApi";
import { fetchWebsiteSettings } from "../PageBuilder/services/PageBuilder.api";
import { readEcommerceThemeCacheSnapshot } from "./utils/ecommerceCatalogCache";
import { MADAR_STORE_THEME, normalizeStoreTheme } from "../../utils/ecommerceTheme";
import { useCommerceI18n } from "../../utils/commerceI18n";

const DEFAULT_THEME = MADAR_STORE_THEME;

const COLOR_FIELDS = [
  ["accent", "mainColor", "mainColorHelp"],
  ["background", "pageBackground", "pageBackgroundHelp"],
  ["surface", "cardsSections", "cardsSectionsHelp"],
  ["text", "mainText", "mainTextHelp"],
  ["muted", "secondaryText", "secondaryTextHelp"],
];

const isHexColor = (value) => /^#[0-9a-f]{6}$/i.test(String(value || ""));
const THEME_PREVIEW_KEY = "madar-online-store-theme-preview";

export default function EcommerceThemePage({ user }) {
  const { t, locale, direction } = useCommerceI18n();
  const cacheScope = user?.id ? `user-${user.id}` : "authenticated";
  const cachedTheme = useMemo(() => readEcommerceThemeCacheSnapshot(cacheScope), [cacheScope]);
  const [theme, setTheme] = useState(() => normalizeStoreTheme(cachedTheme?.theme));
  const [loading, setLoading] = useState(() => !cachedTheme);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);
  const [website, setWebsite] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(true);
  const [frameReady, setFrameReady] = useState(false);
  const [previewMode, setPreviewMode] = useState("desktop");
  const [previewWidth, setPreviewWidth] = useState(720);
  const previewFrameRef = useRef(null);
  const previewShellRef = useRef(null);

  useEffect(() => {
    const shell = previewShellRef.current;
    if (!shell) return undefined;
    const measure = () => { if (shell.clientWidth) setPreviewWidth(shell.clientWidth); };
    measure();
    if (typeof ResizeObserver !== "undefined") {
      const observer = new ResizeObserver(measure);
      observer.observe(shell);
      return () => observer.disconnect();
    }
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [loading]);

  useEffect(() => {
    let cancelled = false;
    fetchEcommerceTheme({ scope: cacheScope, force: Boolean(cachedTheme?.isStale) })
      .then((result) => {
        if (!cancelled) setTheme(normalizeStoreTheme(result?.theme));
      })
      .catch(() => {
        if (!cancelled) setToast({ id: Date.now(), type: "error", title: t("admin.loadColorsError"), message: t("admin.tryAgain") });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [cacheScope, cachedTheme?.isStale, t]);

  useEffect(() => {
    let cancelled = false;
    fetchWebsiteSettings()
      .then((result) => { if (!cancelled) setWebsite(result || null); })
      .catch(() => { if (!cancelled) { setWebsite(null); setToast({ type: "error", title: t("admin.loadSettingsError"), message: t("admin.tryAgain") }); } })
      .finally(() => { if (!cancelled) setPreviewLoading(false); });
    return () => { cancelled = true; };
  }, [t]);

  const valid = useMemo(() => COLOR_FIELDS.every(([key]) => isHexColor(theme[key])), [theme]);
  const subdomain = String(website?.subdomain || "").trim();
  const previewPath = subdomain ? `/site/${encodeURIComponent(subdomain)}/shop?preview=draft` : "";
  const viewportWidth = previewMode === "mobile" ? 390 : 1120;
  const previewScale = Math.min(1, previewWidth / viewportWidth);

  const updateColor = (key, value) => setTheme((current) => ({ ...current, [key]: value.toLowerCase() }));

  const preview = () => {
    if (!valid) {
      setToast({ id: Date.now(), type: "error", title: t("admin.checkColors"), message: t("admin.fixColors") });
      return;
    }
    if (!previewPath) {
      setToast({ id: Date.now(), type: "error", title: t("admin.addressNeeded"), message: t("admin.chooseAddress") });
      return;
    }
    try {
      window.open(previewPath, "_blank", "noopener,noreferrer");
    } catch {
      setToast({ type: "error", title: t("admin.previewUnavailable"), message: t("admin.tryAgain") });
    }
  };

  useEffect(() => {
    if (!valid) return;
    try {
      localStorage.setItem(THEME_PREVIEW_KEY, JSON.stringify(theme));
    } catch {
      notifyCommerceAction({ type: "error", title: t("feedback.draftUnavailable"), message: t("feedback.draftUnavailableBody") });
    }
    previewFrameRef.current?.contentWindow?.postMessage({ type: "madar-online-store-theme-preview", theme }, window.location.origin);
  }, [theme, valid, t]);

  const save = async () => {
    if (!valid) {
      setToast({ id: Date.now(), type: "error", title: t("admin.checkColors"), message: t("admin.colorFormat") });
      return;
    }
    setSaving(true);
    try {
      const result = await saveEcommerceTheme(theme, { scope: cacheScope });
      setTheme({ ...DEFAULT_THEME, ...(result?.theme || theme) });
      try { localStorage.removeItem(THEME_PREVIEW_KEY); } catch { /* Publishing succeeded; local draft storage is optional. */ }
      setToast({ id: Date.now(), type: "success", title: t("admin.designPublished"), message: t("admin.designPublishedBody") });
    } catch {
      setToast({ id: Date.now(), type: "error", title: t("admin.saveColorsError"), message: t("admin.tryAgain") });
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="ecommerce-theme-page" dir={direction} lang={locale}>
      <header className="ecommerce-page-header app-page-intro">
        <div>
          <h1>{t("admin.storeDesign")}</h1>
          <p>{t("admin.storeDesignSubtitle")}</p>
        </div>
      </header>

      {loading ? (
        <div className="ecommerce-theme-skeleton" role="status" aria-label={t("admin.loadingStoreDesign")}><i /><i /><i /><i /><i /><i /></div>
      ) : (
        <div className="ecommerce-theme-layout">
          <section className="ecommerce-theme-controls" aria-label={t("admin.storeColors")}>
            <h2 className="ecommerce-theme-section-title">{t("admin.storeColors")}</h2>
            <div className="ecommerce-theme-color-list">
              {COLOR_FIELDS.map(([key, label, description]) => (
                <label className="ecommerce-theme-color-row" key={key}>
                  <input type="color" value={isHexColor(theme[key]) ? theme[key] : DEFAULT_THEME[key]} onChange={(event) => updateColor(key, event.target.value)} aria-label={t("admin.colorPicker", { label: t(`admin.${label}`) })} />
                  <span><strong>{t(`admin.${label}`)}</strong><small>{t(`admin.${description}`)}</small></span>
                  <input className={!isHexColor(theme[key]) ? "is-invalid" : ""} dir="ltr" value={theme[key]} maxLength={7} spellCheck="false" aria-label={t(`admin.${label}`)} onChange={(event) => updateColor(key, event.target.value)} />
                </label>
              ))}
            </div>

            <button type="button" className="ecommerce-theme-reset" onClick={() => setTheme(DEFAULT_THEME)}><RotateCcw size={16} />{t("admin.restoreColors")}</button>
            <footer className="ecommerce-theme-settings-footer">
              <button type="button" className="ecommerce-primary-button" disabled={saving || loading} onClick={save}>
                {saving ? <LoaderCircle size={18} className="is-spinning" /> : <Rocket size={18} />}
                {saving ? t("admin.publishing") : t("admin.publishChanges")}
              </button>
            </footer>
          </section>

          <aside className="ecommerce-theme-preview" aria-label={t("admin.exactPreview")}>
            <div className="ecommerce-theme-preview-label"><span>{t("admin.customerPreview")}</span><small>{t("admin.previewUpdates")}</small></div>
            <div className="ecommerce-theme-preview-toolbar">
              <div className="ecommerce-theme-device-controls" role="group" aria-label={t("admin.previewDevice")}>
                <button type="button" aria-pressed={previewMode === "desktop"} onClick={() => setPreviewMode("desktop")}><Monitor size={16} />{t("admin.desktopPreview")}</button>
                <button type="button" aria-pressed={previewMode === "mobile"} onClick={() => setPreviewMode("mobile")}><Smartphone size={16} />{t("admin.mobilePreview")}</button>
              </div>
              <button type="button" className="ecommerce-secondary-button" disabled={saving || loading || !previewPath} onClick={preview}><ExternalLink size={16} />{t("admin.openFullPreview")}</button>
            </div>
            <div className="ecommerce-theme-live-shell" ref={previewShellRef}>
              {(previewLoading || (previewPath && !frameReady)) && <div className="ecommerce-theme-frame-skeleton" role="status" aria-label={t("admin.loadingExactPreview")}><i /><i /><i /><i /></div>}
              {!previewLoading && !previewPath && <div className="ecommerce-theme-preview-empty"><strong>{t("admin.setAddress")}</strong><span>{t("admin.openSettingsAddress")}</span></div>}
              {previewPath && <div className="ecommerce-theme-frame-viewport" style={{ width:viewportWidth * previewScale, height:760 * previewScale }}>
                <iframe ref={previewFrameRef} src={previewPath} title={t("admin.draftPreviewTitle")} style={{ width:viewportWidth, height:760, transform:`scale(${previewScale})` }} onLoad={() => { setFrameReady(true); previewFrameRef.current?.contentWindow?.postMessage({ type: "madar-online-store-theme-preview", theme }, window.location.origin); }} />
              </div>}
            </div>
          </aside>
        </div>
      )}

      <AuthToast dir={direction} key={toast?.id} type={toast?.type} title={toast?.title} message={toast?.message} onDismiss={() => setToast(null)} />
    </main>
  );
}
