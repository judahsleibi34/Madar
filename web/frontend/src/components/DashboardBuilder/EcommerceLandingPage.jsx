import { useEffect, useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Check, ImagePlus, LoaderCircle, Plus, Rocket, Sparkles, Trash2 } from "lucide-react";

import EcommerceRouteSkeleton from "./EcommerceRouteSkeleton";
import EcommerceToast from "./EcommerceToast";
import { getEcommerceCacheScope } from "./utils/ecommerceAdminCache";
import {
  fetchEcommerceLandingPage,
  saveEcommerceLandingPage,
  uploadEcommerceProductImage,
} from "../../services/ecommerceApi";
import { createDemoLandingSlides } from "../../config/ecommerceLandingDefaults";
import { useCommerceI18n } from "../../utils/commerceI18n";
import { resolveMediaUrl } from "../../utils/media";

const EMPTY_LANDING_PAGE = { autoplay_enabled: true, interval_ms: 5000, slides: [] };

function newSlide() {
  return {
    id: globalThis.crypto?.randomUUID?.() || `00000000-0000-4000-8000-${Date.now().toString().padStart(12, "0").slice(-12)}`,
    image_url: "",
    title_en: "",
    title_ar: "",
    subtitle_en: "",
    subtitle_ar: "",
  };
}

function normalizeLandingPage(value) {
  const configuredSlides = Array.isArray(value?.slides) ? value.slides.slice(0, 8) : [];
  return {
    autoplay_enabled: value?.autoplay_enabled !== false,
    interval_ms: Math.min(15000, Math.max(3000, Number(value?.interval_ms) || 5000)),
    slides: configuredSlides.length ? configuredSlides : createDemoLandingSlides(),
  };
}

export default function EcommerceLandingPage({ user }) {
  const { t, locale, direction } = useCommerceI18n();
  const cacheScope = getEcommerceCacheScope(user);
  const [landingPage, setLandingPage] = useState(EMPTY_LANDING_PAGE);
  const [activeSlideId, setActiveSlideId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingId, setUploadingId] = useState("");
  const [toast, setToast] = useState(null);

  useEffect(() => {
    let cancelled = false;
    fetchEcommerceLandingPage({ scope: cacheScope })
      .then((result) => {
        if (cancelled) return;
        const next = normalizeLandingPage(result?.landing_page);
        setLandingPage(next);
        setActiveSlideId(next.slides[0]?.id || "");
      })
      .catch(() => {
        if (!cancelled) setToast({ type: "error", title: t("landingAdmin.loadError"), message: t("admin.tryAgain") });
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [cacheScope, t]);

  const activeSlideIndex = useMemo(
    () => Math.max(0, landingPage.slides.findIndex((slide) => slide.id === activeSlideId)),
    [activeSlideId, landingPage.slides],
  );
  const activeSlide = landingPage.slides[activeSlideIndex] || null;

  const updateSlide = (slideId, patch) => {
    setLandingPage((current) => ({
      ...current,
      slides: current.slides.map((slide) => slide.id === slideId ? { ...slide, ...patch } : slide),
    }));
  };

  const addSlide = () => {
    const slide = newSlide();
    setLandingPage((current) => ({ ...current, slides: [...current.slides, slide] }));
    setActiveSlideId(slide.id);
  };

  const removeSlide = (slideId) => {
    setLandingPage((current) => {
      const removedIndex = current.slides.findIndex((slide) => slide.id === slideId);
      const slides = current.slides.filter((slide) => slide.id !== slideId);
      setActiveSlideId(slides[Math.min(Math.max(removedIndex, 0), slides.length - 1)]?.id || "");
      return { ...current, slides };
    });
  };

  const moveSlide = (index, offset) => {
    const target = index + offset;
    if (target < 0 || target >= landingPage.slides.length) return;
    setLandingPage((current) => {
      const slides = [...current.slides];
      [slides[index], slides[target]] = [slides[target], slides[index]];
      return { ...current, slides };
    });
  };

  const uploadSlideImage = async (slideId, file) => {
    if (!file) return;
    setUploadingId(slideId);
    try {
      const imageUrl = await uploadEcommerceProductImage(file);
      if (!imageUrl) throw new Error("missing image URL");
      updateSlide(slideId, { image_url: imageUrl });
    } catch {
      setToast({ type: "error", title: t("landingAdmin.uploadError"), message: t("admin.tryAgain") });
    } finally {
      setUploadingId("");
    }
  };

  const publish = async () => {
    if (landingPage.slides.some((slide) => !slide.image_url)) {
      setToast({ type: "error", title: t("landingAdmin.imageRequired"), message: t("admin.tryAgain") });
      return;
    }
    setSaving(true);
    try {
      const result = await saveEcommerceLandingPage(landingPage, { scope: cacheScope });
      const next = normalizeLandingPage(result?.landing_page || landingPage);
      setLandingPage(next);
      setActiveSlideId((current) => next.slides.some((slide) => slide.id === current) ? current : next.slides[0]?.id || "");
      setToast({ type: "success", title: t("landingAdmin.published"), message: t("landingAdmin.publishedBody") });
    } catch {
      setToast({ type: "error", title: t("landingAdmin.saveError"), message: t("admin.tryAgain") });
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <EcommerceRouteSkeleton pathname="/ecommerce/landing-page" label={t("common.loading")} direction={direction} lang={locale} />;

  const localizedTitle = activeSlide && (locale === "ar" ? activeSlide.title_ar || activeSlide.title_en : activeSlide.title_en || activeSlide.title_ar);
  const localizedSubtitle = activeSlide && (locale === "ar" ? activeSlide.subtitle_ar || activeSlide.subtitle_en : activeSlide.subtitle_en || activeSlide.subtitle_ar);

  return (
    <main className="ecommerce-landing-admin" dir={direction} lang={locale}>
      <header className="ecommerce-page-header app-page-intro ecommerce-landing-heading">
        <div>
          <span className="ecommerce-page-kicker">{t("landingAdmin.kicker")}</span>
          <h1>{t("landingAdmin.title")}</h1>
          <p>{t("landingAdmin.subtitle")}</p>
        </div>
        <button type="button" className="ecommerce-primary-button" disabled={saving || !landingPage.slides.length} onClick={publish}>
          {saving ? <LoaderCircle className="is-spinning" size={18} /> : <Rocket size={18} />}
          {t(saving ? "landingAdmin.publishing" : "landingAdmin.publish")}
        </button>
      </header>

      <section className="ecommerce-landing-settings" aria-labelledby="landing-carousel-settings-title">
        <div className="ecommerce-landing-settings-intro">
          <span><Sparkles size={19} /></span>
          <div><h2 id="landing-carousel-settings-title">{t("landingAdmin.settings")}</h2><p>{t("landingAdmin.autoplayHelp")}</p></div>
        </div>
        <label className="ecommerce-landing-toggle">
          <input type="checkbox" checked={landingPage.autoplay_enabled} onChange={(event) => setLandingPage((current) => ({ ...current, autoplay_enabled: event.target.checked }))} />
          <span className="ecommerce-landing-switch" aria-hidden="true"><i /></span>
          <span>{t("landingAdmin.autoplay")}</span>
        </label>
        <label className="ecommerce-landing-interval">
          <span>{t("landingAdmin.interval")}</span>
          <span><input type="number" min="3" max="15" value={landingPage.interval_ms / 1000} onChange={(event) => setLandingPage((current) => ({ ...current, interval_ms: Math.min(15, Math.max(3, Number(event.target.value) || 3)) * 1000 }))} /><small>{t("landingAdmin.seconds")}</small></span>
        </label>
        <div className="ecommerce-landing-ready"><Check size={17} /><span>{t("landingAdmin.slideCount", { count: landingPage.slides.length })}</span></div>
      </section>

      <section className="ecommerce-landing-workspace">
        <header className="ecommerce-landing-workspace-header">
          <div><h2>{t("landingAdmin.slides")}</h2><p>{t("landingAdmin.slidesHelp")}</p></div>
          <button type="button" onClick={addSlide} disabled={landingPage.slides.length >= 8}><Plus size={17} />{t("landingAdmin.addSlide")}</button>
        </header>

        <div className="ecommerce-landing-slide-rail" role="tablist" aria-label={t("landingAdmin.slides")}>
          {landingPage.slides.map((slide, index) => {
            const slideTitle = locale === "ar" ? slide.title_ar || slide.title_en : slide.title_en || slide.title_ar;
            return (
              <button type="button" role="tab" aria-selected={activeSlide?.id === slide.id} className={activeSlide?.id === slide.id ? "is-active" : ""} key={slide.id} onClick={() => setActiveSlideId(slide.id)}>
                <span className="ecommerce-landing-slide-thumb">{slide.image_url ? <img src={resolveMediaUrl(slide.image_url)} alt="" /> : <ImagePlus size={20} />}</span>
                <span><small>{t("landingAdmin.slide", { number: index + 1 })}</small><b>{slideTitle || t("landingAdmin.untitled")}</b></span>
              </button>
            );
          })}
        </div>

        {activeSlide ? (
          <div className="ecommerce-landing-layout">
            <article className="ecommerce-landing-editor" aria-label={t("landingAdmin.editSlide", { number: activeSlideIndex + 1 })}>
              <header>
                <div><span>{t("landingAdmin.selectedSlide")}</span><h2>{t("landingAdmin.slide", { number: activeSlideIndex + 1 })}</h2></div>
                <div>
                  <button type="button" disabled={activeSlideIndex === 0} onClick={() => moveSlide(activeSlideIndex, -1)} aria-label={t("landingAdmin.moveUp", { number: activeSlideIndex + 1 })}><ArrowUp size={17} /></button>
                  <button type="button" disabled={activeSlideIndex === landingPage.slides.length - 1} onClick={() => moveSlide(activeSlideIndex, 1)} aria-label={t("landingAdmin.moveDown", { number: activeSlideIndex + 1 })}><ArrowDown size={17} /></button>
                  <button type="button" className="is-danger" onClick={() => removeSlide(activeSlide.id)} aria-label={t("landingAdmin.deleteSlide", { number: activeSlideIndex + 1 })}><Trash2 size={17} /></button>
                </div>
              </header>

              <label className="ecommerce-landing-image-field">
                {activeSlide.image_url ? <img src={resolveMediaUrl(activeSlide.image_url)} alt="" /> : <span><ImagePlus size={28} />{t("landingAdmin.image")}</span>}
                <b><ImagePlus size={16} />{uploadingId === activeSlide.id ? t("landingAdmin.uploading") : t(activeSlide.image_url ? "landingAdmin.replaceImage" : "landingAdmin.uploadImage")}</b>
                <input type="file" accept="image/png,image/jpeg,image/webp" disabled={uploadingId === activeSlide.id} onChange={(event) => { const file = event.currentTarget.files?.[0]; event.currentTarget.value = ""; void uploadSlideImage(activeSlide.id, file); }} />
              </label>

              <div className="ecommerce-landing-editor-copy">
                <div><h3>{t("landingAdmin.content")}</h3><p>{t("landingAdmin.contentHelp")}</p></div>
                <div className="ecommerce-landing-language-grid">
                  {[[ "en", "landingAdmin.englishContent", "ltr" ], [ "ar", "landingAdmin.arabicContent", "rtl" ]].map(([language, label, dir]) => (
                    <fieldset key={language} dir={dir}><legend>{t(label)}</legend>
                      <label>{t("landingAdmin.headline")}<input value={activeSlide[`title_${language}`]} maxLength={120} onChange={(event) => updateSlide(activeSlide.id, { [`title_${language}`]: event.target.value })} /></label>
                      <label>{t("landingAdmin.description")}<textarea value={activeSlide[`subtitle_${language}`]} maxLength={320} rows={3} onChange={(event) => updateSlide(activeSlide.id, { [`subtitle_${language}`]: event.target.value })} /></label>
                    </fieldset>
                  ))}
                </div>
              </div>
            </article>

            <aside className="ecommerce-landing-preview" aria-label={t("landingAdmin.preview")}>
              <header><div><span className="ecommerce-landing-live-dot" />{t("landingAdmin.livePreview")}</div><small>{t("landingAdmin.desktopPreview")}</small></header>
              <div className="ecommerce-landing-preview-browser">
                <div className="ecommerce-landing-preview-browser-bar"><i /><i /><i /><span /></div>
                <div className="ecommerce-landing-preview-frame">
                  {activeSlide.image_url && <img src={resolveMediaUrl(activeSlide.image_url)} alt="" />}
                  <div><h3>{localizedTitle}</h3><p>{localizedSubtitle}</p></div>
                  <nav aria-hidden="true">{landingPage.slides.map((slide) => <i className={slide.id === activeSlide.id ? "is-active" : ""} key={slide.id} />)}</nav>
                </div>
              </div>
              <p className="ecommerce-landing-preview-note">{t("landingAdmin.previewHelp")}</p>
            </aside>
          </div>
        ) : <div className="ecommerce-landing-empty"><ImagePlus size={30} /><h3>{t("landingAdmin.emptyTitle")}</h3><p>{t("landingAdmin.emptyPreview")}</p><button type="button" onClick={addSlide}><Plus size={17} />{t("landingAdmin.addSlide")}</button></div>}
      </section>
      <EcommerceToast {...toast} dir={direction} onDismiss={() => setToast(null)} />
    </main>
  );
}
