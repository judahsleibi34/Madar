import { useEffect, useMemo, useRef, useState } from "react";
import { ExternalLink, LoaderCircle, RotateCcw, Rocket } from "lucide-react";

import AuthToast from "../AuthPages/AuthToast";
import { fetchEcommerceCatalog, fetchEcommerceGrowth, fetchEcommerceTheme, saveEcommerceGrowth, saveEcommerceTheme } from "../../services/ecommerceApi";
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

const EMPTY_GROWTH = {
  seo_title_en: "", seo_title_ar: "",
  seo_description_en: "", seo_description_ar: "",
  announcement_enabled: false,
  announcement_text_en: "", announcement_text_ar: "", announcement_link: "",
  featured_product_ids: [], featured_category_ids: [],
};

const translatedName = (item, locale) => {
  const translations = item?.translations || {};
  return translations?.[locale]?.name || translations?.en?.name || translations?.ar?.name || item?.slug || "";
};

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
  const [growth, setGrowth] = useState(EMPTY_GROWTH);
  const [catalog, setCatalog] = useState({ products: [], categories: [] });
  const [website, setWebsite] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(true);
  const [frameReady, setFrameReady] = useState(false);
  const previewFrameRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    fetchEcommerceTheme({ scope: cacheScope, force: Boolean(cachedTheme?.isStale) })
      .then((result) => {
        if (!cancelled) setTheme(normalizeStoreTheme(result?.theme));
      })
      .catch((error) => {
        if (!cancelled) setToast({ id: Date.now(), type: "error", title: t("admin.loadColorsError"), message: error.message || t("admin.tryAgain") });
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
      .catch(() => { if (!cancelled) setWebsite(null); })
      .finally(() => { if (!cancelled) setPreviewLoading(false); });
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchEcommerceGrowth(), fetchEcommerceCatalog({ scope: cacheScope })])
      .then(([growthResult, catalogResult]) => {
        if (cancelled) return;
        setGrowth({ ...EMPTY_GROWTH, ...(growthResult?.growth || {}) });
        setCatalog(catalogResult || { products: [], categories: [] });
      })
      .catch((error) => { if (!cancelled) setToast({ id: Date.now(), type: "error", title: t("admin.growthLoadError"), message: error.message || t("admin.tryAgain") }); });
    return () => { cancelled = true; };
  }, [cacheScope, t]);

  const valid = useMemo(() => COLOR_FIELDS.every(([key]) => isHexColor(theme[key])), [theme]);
  const subdomain = String(website?.subdomain || "").trim();
  const previewPath = subdomain ? `/site/${encodeURIComponent(subdomain)}/shop?preview=draft` : "";

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
    window.open(previewPath, "_blank", "noopener,noreferrer");
  };

  useEffect(() => {
    if (!valid) return;
    localStorage.setItem(THEME_PREVIEW_KEY, JSON.stringify(theme));
    previewFrameRef.current?.contentWindow?.postMessage({ type: "madar-online-store-theme-preview", theme }, window.location.origin);
  }, [theme, valid]);

  const save = async () => {
    if (!valid) {
      setToast({ id: Date.now(), type: "error", title: t("admin.checkColors"), message: t("admin.colorFormat") });
      return;
    }
    setSaving(true);
    try {
      const result = await saveEcommerceTheme(theme, { scope: cacheScope });
      setTheme({ ...DEFAULT_THEME, ...(result?.theme || theme) });
      localStorage.removeItem(THEME_PREVIEW_KEY);
      setToast({ id: Date.now(), type: "success", title: t("admin.designPublished"), message: t("admin.designPublishedBody") });
    } catch (error) {
      setToast({ id: Date.now(), type: "error", title: t("admin.saveColorsError"), message: error.message || t("admin.tryAgain") });
    } finally {
      setSaving(false);
    }
  };

  const saveGrowth = async () => {
    setSaving(true);
    try {
      const result = await saveEcommerceGrowth(growth);
      setGrowth({ ...EMPTY_GROWTH, ...(result?.growth || growth) });
      setToast({ id: Date.now(), type: "success", title: t("admin.growthSaved"), message: t("admin.growthSavedBody") });
    } catch (error) {
      setToast({ id: Date.now(), type: "error", title: t("admin.growthSaveError"), message: error.message || t("admin.tryAgain") });
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
        <div className="ecommerce-page-actions">
          <button type="button" className="ecommerce-secondary-button" disabled={saving || loading || !previewPath} onClick={preview}><ExternalLink size={18} />{t("admin.openFullPreview")}</button>
          <button type="button" className="ecommerce-primary-button" disabled={saving || loading} onClick={save}>
          {saving ? <LoaderCircle size={18} className="is-spinning" /> : <Rocket size={18} />}
          {saving ? t("admin.publishing") : t("admin.publishChanges")}
          </button>
        </div>
      </header>

      {loading ? (
        <div className="ecommerce-theme-skeleton" role="status" aria-label={t("admin.loadingStoreDesign")}><i /><i /><i /><i /><i /><i /></div>
      ) : (
        <div className="ecommerce-theme-layout">
          <section className="ecommerce-theme-controls" aria-label={t("admin.storeColors")}>
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

            <section className="ecommerce-growth-controls" aria-labelledby="store-growth-title">
              <div><h2 id="store-growth-title">{t("admin.growthTitle")}</h2><p>{t("admin.growthHelp")}</p></div>
              <label>{t("admin.seoTitleEnglish")}<input maxLength={120} value={growth.seo_title_en} onChange={(event) => setGrowth((current) => ({ ...current, seo_title_en: event.target.value }))} /></label>
              <label>{t("admin.seoTitleArabic")}<input dir="rtl" maxLength={120} value={growth.seo_title_ar} onChange={(event) => setGrowth((current) => ({ ...current, seo_title_ar: event.target.value }))} /></label>
              <label>{t("admin.seoDescriptionEnglish")}<textarea maxLength={320} value={growth.seo_description_en} onChange={(event) => setGrowth((current) => ({ ...current, seo_description_en: event.target.value }))} /></label>
              <label>{t("admin.seoDescriptionArabic")}<textarea dir="rtl" maxLength={320} value={growth.seo_description_ar} onChange={(event) => setGrowth((current) => ({ ...current, seo_description_ar: event.target.value }))} /></label>
              <label className="ecommerce-growth-toggle"><input type="checkbox" checked={growth.announcement_enabled} onChange={(event) => setGrowth((current) => ({ ...current, announcement_enabled: event.target.checked }))} /><span>{t("admin.announcementEnabled")}</span></label>
              <label>{t("admin.announcementEnglish")}<input maxLength={240} value={growth.announcement_text_en} onChange={(event) => setGrowth((current) => ({ ...current, announcement_text_en: event.target.value }))} /></label>
              <label>{t("admin.announcementArabic")}<input dir="rtl" maxLength={240} value={growth.announcement_text_ar} onChange={(event) => setGrowth((current) => ({ ...current, announcement_text_ar: event.target.value }))} /></label>
              <label>{t("admin.announcementLink")}<input dir="ltr" maxLength={500} placeholder="/shop/catalog or https://example.com" value={growth.announcement_link} onChange={(event) => setGrowth((current) => ({ ...current, announcement_link: event.target.value }))} /></label>
              <label>{t("admin.featuredProducts")}<select multiple value={growth.featured_product_ids} onChange={(event) => setGrowth((current) => ({ ...current, featured_product_ids: Array.from(event.target.selectedOptions, (option) => option.value) }))}>{(catalog.products || []).filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{translatedName(item, locale)}</option>)}</select></label>
              <label>{t("admin.featuredCategories")}<select multiple value={growth.featured_category_ids} onChange={(event) => setGrowth((current) => ({ ...current, featured_category_ids: Array.from(event.target.selectedOptions, (option) => option.value) }))}>{(catalog.categories || []).filter((item) => item.status === "active").map((item) => <option key={item.id} value={item.id}>{translatedName(item, locale)}</option>)}</select></label>
              <small>{t("admin.featuredSelectionHelp")}</small>
              <button type="button" className="ecommerce-primary-button" disabled={saving || loading} onClick={saveGrowth}>{saving ? <LoaderCircle size={18} className="is-spinning" /> : <Rocket size={18} />}{saving ? t("admin.saving") : t("admin.saveGrowth")}</button>
            </section>
          </section>

          <aside className="ecommerce-theme-preview" aria-label={t("admin.exactPreview")}>
            <div className="ecommerce-theme-preview-label"><span>{t("admin.customerPreview")}</span><small>{t("admin.previewUpdates")}</small></div>
            <div className="ecommerce-theme-live-shell">
              {(previewLoading || (previewPath && !frameReady)) && <div className="ecommerce-theme-frame-skeleton" role="status" aria-label={t("admin.loadingExactPreview")}><i /><i /><i /><i /></div>}
              {!previewLoading && !previewPath && <div className="ecommerce-theme-preview-empty"><strong>{t("admin.setAddress")}</strong><span>{t("admin.openSettingsAddress")}</span></div>}
              {previewPath && <iframe ref={previewFrameRef} src={previewPath} title={t("admin.draftPreviewTitle")} onLoad={() => { setFrameReady(true); previewFrameRef.current?.contentWindow?.postMessage({ type: "madar-online-store-theme-preview", theme }, window.location.origin); }} />}
            </div>
          </aside>
        </div>
      )}

      <AuthToast key={toast?.id} type={toast?.type} title={toast?.title} message={toast?.message} onDismiss={() => setToast(null)} />
    </main>
  );
}
