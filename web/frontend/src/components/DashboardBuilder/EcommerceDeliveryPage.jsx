import { useEffect, useMemo, useState } from "react";
import { LoaderCircle, MapPin, RotateCcw, Save, Search } from "lucide-react";

import AuthToast from "../AuthPages/AuthToast";
import { fetchEcommerceDeliveryAreas, saveEcommerceDeliveryAreas } from "../../services/ecommerceApi";
import { useCommerceI18n } from "../../utils/commerceI18n";

export default function EcommerceDeliveryPage() {
  const { t, locale, direction } = useCommerceI18n();
  const [areas, setAreas] = useState([]);
  const [savedIds, setSavedIds] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  const load = () => {
    setLoading(true);
    fetchEcommerceDeliveryAreas()
      .then((result) => {
        const nextAreas = result?.areas || [];
        const enabled = nextAreas.filter((area) => area.enabled).map((area) => area.id);
        setAreas(nextAreas);
        setSavedIds(enabled);
        setSelectedIds(enabled);
      })
      .catch((error) => setToast({ type: "error", title: t("admin.loadDelivery"), message: error.message }))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    let cancelled = false;
    fetchEcommerceDeliveryAreas()
      .then((result) => {
        if (cancelled) return;
        const nextAreas = result?.areas || [];
        const enabled = nextAreas.filter((area) => area.enabled).map((area) => area.id);
        setAreas(nextAreas);
        setSavedIds(enabled);
        setSelectedIds(enabled);
      })
      .catch((error) => { if (!cancelled) setToast({ type: "error", title: t("admin.loadDelivery"), message: error.message }); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [t]);
  const dirty = useMemo(() => [...selectedIds].sort().join() !== [...savedIds].sort().join(), [selectedIds, savedIds]);
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
  const save = async () => {
    setSaving(true);
    try {
      await saveEcommerceDeliveryAreas(selectedIds);
      setSavedIds(selectedIds);
      setToast({ type: "success", title: t("admin.deliverySaved"), message: t("admin.deliverySavedBody", { count: selectedIds.length }) });
    } catch (error) {
      setToast({ type: "error", title: t("admin.saveDeliveryError"), message: error.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="ecommerce-page ecommerce-operations-page" dir={direction} lang={locale}>
      <header className="ecommerce-page-header app-page-intro">
        <div><h1>{t("merchant.deliveryTitle")}</h1><p>{t("merchant.deliverySubtitle")}</p></div>
        <div className="ecommerce-page-actions">
          <button type="button" className="ecommerce-secondary-button" disabled={loading || saving} onClick={load}><RotateCcw size={18} />{t("common.retry")}</button>
          <button type="button" className="ecommerce-primary-button" disabled={loading || saving || !dirty} onClick={save}>{saving ? <LoaderCircle className="is-spinning" size={18} /> : <Save size={18} />}{saving ? t("merchant.saving") : t("merchant.saveDelivery")}</button>
        </div>
      </header>

      <section className="ecommerce-operations-card">
        <div className="ecommerce-operations-toolbar">
          <label><Search size={17} /><input aria-label={t("merchant.searchAreas")} value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t("merchant.searchAreas")} /></label>
          <strong>{t("merchant.enabledCount", { count: selectedIds.length })}</strong>
        </div>
        {loading ? <div className="ecommerce-operations-state" role="status"><LoaderCircle className="is-spinning" />{t("admin.loadingDelivery")}</div> : (
          <div className="ecommerce-delivery-grid">
            {visible.map((area) => (
              <label key={area.id} className={selectedIds.includes(area.id) ? "is-enabled" : ""}>
                <input type="checkbox" checked={selectedIds.includes(area.id)} onChange={() => toggle(area.id)} />
                <MapPin size={19} aria-hidden="true" />
                <span><strong>{locale === "ar" ? area.name_ar || area.name_en : area.name_en || area.name_ar}</strong><small>{area.code}</small></span>
              </label>
            ))}
          </div>
        )}
        {!loading && !areas.length && <div className="ecommerce-operations-state">{t("admin.noDeliveryAreas")}</div>}
        {!loading && areas.length > 0 && selectedIds.length === 0 && <p className="ecommerce-operations-warning">{t("admin.deliveryRequired")}</p>}
      </section>
      <AuthToast key={toast?.id} type={toast?.type} title={toast?.title} message={toast?.message} onDismiss={() => setToast(null)} />
    </main>
  );
}
