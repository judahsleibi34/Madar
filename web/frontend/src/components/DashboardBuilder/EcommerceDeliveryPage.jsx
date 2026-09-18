import { getEcommerceCacheScope, readEcommerceAdminCacheSnapshot } from "./utils/ecommerceAdminCache";
import { useEffect, useMemo, useState } from "react";
import { LoaderCircle, MapPin, Plus, Save, Search, Trash2, X } from "lucide-react";

import AuthToast from "../AuthPages/AuthToast";
import EcommerceOperationsSkeleton from "./EcommerceOperationsSkeleton";
import { createEcommerceDeliveryLocation, fetchEcommerceDeliveryAreas, saveEcommerceDeliveryAreas } from "../../services/ecommerceApi";
import { useCommerceI18n } from "../../utils/commerceI18n";

export default function EcommerceDeliveryPage({ user }) {
  const cacheScope = getEcommerceCacheScope(user);
  const { t, locale, direction } = useCommerceI18n();
  const snapshot = readEcommerceAdminCacheSnapshot(cacheScope, "delivery-areas");
  const initialAreas = snapshot?.data?.areas || [];
  const initialIds = initialAreas.filter(area => area.enabled).map(area => area.id);
  const [areas, setAreas] = useState(() => initialAreas);
  const [savedIds, setSavedIds] = useState(() => initialIds);
  const [selectedIds, setSelectedIds] = useState(() => initialIds);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(() => !snapshot);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);
  const [locationOpen, setLocationOpen] = useState(false);
  const [location, setLocation] = useState({ country: "", country_ar: "", levels: ["", ""], levels_ar: ["", ""] });
  const [creating, setCreating] = useState(false);
  const [locationError, setLocationError] = useState("");


  useEffect(() => {
    let cancelled = false;
    const previousIds = (readEcommerceAdminCacheSnapshot(cacheScope, "delivery-areas")?.data?.areas || []).filter(area => area.enabled).map(area => area.id);
    fetchEcommerceDeliveryAreas({ scope: cacheScope })
      .then((result) => {
        if (cancelled) return;
        const nextAreas = result?.areas || [];
        const enabled = nextAreas.filter((area) => area.enabled).map((area) => area.id);
        setAreas(nextAreas);
        setSavedIds(enabled);
        setSelectedIds(current => [...current].sort().join() === [...previousIds].sort().join() ? enabled : current);
      })
      .catch(() => { if (!cancelled) setToast({ type: "error", title: t("admin.loadDelivery"), message: t("admin.tryAgain") }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [cacheScope, t]);
  const dirty = useMemo(() => [...selectedIds].sort().join() !== [...savedIds].sort().join(), [selectedIds, savedIds]);
  useEffect(() => {
    if (!locationOpen) return undefined;
    const overflow = document.body.style.overflow;
    const escape = (event) => { if (event.key === "Escape" && !creating) setLocationOpen(false); };
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", escape);
    return () => { document.body.style.overflow = overflow; document.removeEventListener("keydown", escape); };
  }, [creating, locationOpen]);
  useEffect(() => {
    if (!dirty) return undefined;
    const warn = (event) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    return areas.filter((area) => !query || `${area.name_en} ${area.name_ar} ${area.code}`.toLowerCase().includes(query));
  }, [areas, search]);

  const toggle = (id) => setSelectedIds((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  const createLocation = async (event) => {
    event.preventDefault();
    if (creating) return;
    setCreating(true);
    setLocationError("");
    try {
      const result = await createEcommerceDeliveryLocation({
        country: location.country.trim(),
        levels: location.levels.map((level, index) => level.trim() || location.levels_ar[index].trim()).filter(Boolean),
        name_ar: location.country_ar.trim() || location.levels_ar.some((level) => level.trim()) ? [location.country_ar.trim() || location.country.trim(), ...location.levels.map((level, index) => location.levels_ar[index].trim() || level.trim()).filter(Boolean)].join(" / ") : "",
      }, { scope: cacheScope });
      if (!result?.area?.id) throw new Error(t("admin.saveDeliveryError"));
      setAreas((current) => [...current, result.area]);
      setSelectedIds((current) => [...current, result.area.id]);
      setSearch("");
      setLocationOpen(false);
      setToast({ type: "success", title: t("feedback.locationCreated"), message: t("feedback.locationCreatedBody") });
    } catch {
      setLocationError(t("admin.saveDeliveryError"));
      setToast({ type: "error", title: t("admin.saveDeliveryError"), message: t("admin.tryAgain") });
    } finally {
      setCreating(false);
    }
  };
  const save = async () => {
    setSaving(true);
    try {
      await saveEcommerceDeliveryAreas(selectedIds, { scope: cacheScope });
      setSavedIds(selectedIds);
      setToast({ type: "success", title: t("admin.deliverySaved"), message: t("admin.deliverySavedBody", { count: selectedIds.length }) });
    } catch {
      setToast({ type: "error", title: t("admin.saveDeliveryError"), message: t("admin.tryAgain") });
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="ecommerce-page ecommerce-operations-page ecommerce-delivery-page" dir={direction} lang={locale}>
      <header className="ecommerce-page-header app-page-intro">
        <div><h1>{t("merchant.deliveryTitle")}</h1><p>{t("merchant.deliverySubtitle")}</p></div>
      </header>
        <div className="ecommerce-page-actions ecommerce-delivery-actions">
          <button type="button" className="ecommerce-primary-button" disabled={loading || saving} onClick={() => { setLocation({ country: "", country_ar: "", levels: ["", ""], levels_ar: ["", ""] }); setLocationError(""); setLocationOpen(true); }}><Plus size={18} />{t("merchant.addCustomLocation")}</button>
          <button type="button" className="ecommerce-primary-button" disabled={loading || saving || !dirty} onClick={save}>{saving ? <LoaderCircle className="is-spinning" size={18} /> : <Save size={18} />}{saving ? t("merchant.saving") : t("merchant.saveDelivery")}</button>
        </div>

      <section className="ecommerce-operations-card">
        <div className="ecommerce-operations-toolbar">
          <label className="ecommerce-search"><Search size={17} /><input aria-label={t("merchant.searchAreas")} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("merchant.searchAreas")} /></label>
          <strong>{t("merchant.enabledCount", { count: selectedIds.length })}</strong>
        </div>
        {loading ? <EcommerceOperationsSkeleton variant="delivery" label={t("admin.loadingDelivery")} /> : (
          <div className="ecommerce-delivery-grid">
            {visible.map((area) => (
              <label key={area.id} className={selectedIds.includes(area.id) ? "is-enabled" : ""}>
                <input type="checkbox" checked={selectedIds.includes(area.id)} onChange={() => toggle(area.id)} />
                <MapPin size={19} aria-hidden="true" />
                <span><strong>{locale === "ar" ? area.name_ar || area.name_en : area.name_en || area.name_ar}</strong>{!area.code?.startsWith("custom-") && <small>{area.code}</small>}</span>
              </label>
            ))}
          </div>
        )}
        {!loading && !areas.length && <div className="ecommerce-operations-state">{t("admin.noDeliveryAreas")}</div>}
      </section>
      {locationOpen && <div className="ecommerce-product-editor-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget && !creating) setLocationOpen(false); }}>
        <section className="ecommerce-delivery-location-dialog" role="dialog" aria-modal="true" aria-labelledby="custom-location-title">
          <header><h2 id="custom-location-title">{t("merchant.addCustomLocation")}</h2><button type="button" disabled={creating} aria-label={t("admin.close")} onClick={() => setLocationOpen(false)}><X size={20} /></button></header>
          <form onSubmit={createLocation}>
            <div className="ecommerce-location-language-head"><span>{t("merchant.locationDetails")}</span><span>{t("merchant.locationArabicLanguage")}</span></div>
            <div className="ecommerce-location-language-pair"><label>{t("merchant.locationCountry")}<input aria-label={t("merchant.locationCountry")} autoFocus required maxLength={100} disabled={creating} value={location.country} placeholder={t("merchant.locationCountryExample")} onChange={(event) => setLocation((current) => ({ ...current, country: event.target.value }))} /></label><label>{t("merchant.locationCountry")}<input aria-label={t("merchant.locationCountryArabic")} dir="rtl" maxLength={100} disabled={creating} value={location.country_ar} onChange={(event) => setLocation((current) => ({ ...current, country_ar: event.target.value }))} /></label></div>
            {location.levels.map((level, index) => <div className="ecommerce-location-level-field" key={index}><div className="ecommerce-location-language-pair"><label>{t(index === 0 ? "merchant.locationRegionShort" : index === 1 ? "merchant.locationCityShort" : "merchant.locationOtherShort")}<input aria-label={t(index === 0 ? "merchant.locationRegion" : index === 1 ? "merchant.locationCity" : "merchant.locationOther")} maxLength={100} disabled={creating} value={level} onChange={(event) => setLocation((current) => ({ ...current, levels: current.levels.map((value, position) => position === index ? event.target.value : value) }))} /></label><label>{t(index === 0 ? "merchant.locationRegionShort" : index === 1 ? "merchant.locationCityShort" : "merchant.locationOtherShort")}<input aria-label={t(index === 0 ? "merchant.locationRegionArabic" : index === 1 ? "merchant.locationCityArabic" : "merchant.locationOtherArabic")} dir="rtl" maxLength={100} disabled={creating} value={location.levels_ar[index]} onChange={(event) => setLocation((current) => ({ ...current, levels_ar: current.levels_ar.map((value, position) => position === index ? event.target.value : value) }))} /></label></div>{index >= 2 && <button type="button" disabled={creating} aria-label={t("merchant.removeLocationLevel", { number: index + 1 })} onClick={() => setLocation((current) => ({ ...current, levels: current.levels.filter((_, position) => position !== index), levels_ar: current.levels_ar.filter((_, position) => position !== index) }))}><Trash2 size={16} /></button>}</div>)}
            <button type="button" className="ecommerce-secondary-button" disabled={creating || location.levels.length >= 5} onClick={() => setLocation((current) => ({ ...current, levels: [...current.levels, ""], levels_ar: [...current.levels_ar, ""] }))}><Plus size={16} />{t("merchant.addLocationLevel")}</button>
            {locationError && <p>{locationError}</p>}
            <footer><button type="button" className="ecommerce-secondary-button" disabled={creating} onClick={() => setLocationOpen(false)}>{t("common.cancel")}</button><button type="submit" className="ecommerce-primary-button" disabled={creating || !location.country.trim()}>{creating ? <LoaderCircle className="is-spinning" size={17} /> : <Plus size={17} />}{t("merchant.addLocation")}</button></footer>
          </form>
        </section>
      </div>}
      <AuthToast dir={direction} key={toast?.id} type={toast?.type} title={toast?.title} message={toast?.message} onDismiss={() => setToast(null)} />
    </main>
  );
}
