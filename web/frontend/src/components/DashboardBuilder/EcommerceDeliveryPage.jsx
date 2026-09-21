import PageHeaderSkeleton from "../common/PageHeaderSkeleton";
import { getEcommerceCacheScope, readEcommerceAdminCacheSnapshot } from "./utils/ecommerceAdminCache";
import { useEffect, useMemo, useState } from "react";
import { LoaderCircle, MapPin, Plus, Save, Search, Trash2, X } from "lucide-react";

import AuthToast from "../AuthPages/AuthToast";
import EcommerceOperationsSkeleton from "./EcommerceOperationsSkeleton";
import {
  createEcommerceDeliveryLocation,
  deleteEcommerceDeliveryLocation,
  fetchEcommerceDeliveryAreas,
  fetchEcommerceDeliveryPricing,
  saveEcommerceDeliveryAreas,
  saveEcommerceDeliveryPricing,
} from "../../services/ecommerceApi";
import { useCommerceI18n } from "../../utils/commerceI18n";

export default function EcommerceDeliveryPage({ user }) {
  const cacheScope = getEcommerceCacheScope(user);
  const { t, locale, direction } = useCommerceI18n();
  const snapshot = readEcommerceAdminCacheSnapshot(cacheScope, "delivery-areas");
  const initialAreas = snapshot?.data?.areas || [];
  const initialIds = initialAreas.filter((area) => area.enabled).map((area) => area.id);
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
  const [deletingId, setDeletingId] = useState("");
  const [locationError, setLocationError] = useState("");

  const [pricing, setPricing] = useState(() => {
    const cached = readEcommerceAdminCacheSnapshot(cacheScope, "delivery-pricing");
    return cached?.data?.pricing || [];
  });
  const [pricingDirty, setPricingDirty] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const previousIds = (readEcommerceAdminCacheSnapshot(cacheScope, "delivery-areas")?.data?.areas || [])
      .filter((area) => area.enabled)
      .map((area) => area.id);
    fetchEcommerceDeliveryAreas({ scope: cacheScope })
      .then((result) => {
        if (cancelled) return;
        const nextAreas = result?.areas || [];
        const enabled = nextAreas.filter((area) => area.enabled).map((area) => area.id);
        setAreas(nextAreas);
        setSavedIds(enabled);
        setSelectedIds(
          (current) => ([...current].sort().join() === [...previousIds].sort().join() ? enabled : current)
        );
      })
      .catch(() => {
        if (!cancelled) setToast({ type: "error", title: t("admin.loadDelivery"), message: t("admin.tryAgain") });
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [cacheScope, t]);

  useEffect(() => {
    let cancelled = false;
    fetchEcommerceDeliveryPricing({ scope: cacheScope })
      .then((result) => {
        if (cancelled) return;
        const nextPricing = result?.pricing || [];
        setPricing(nextPricing);
      })
      .catch(() => {
        if (!cancelled) setToast({ type: "error", title: t("merchant.loadPricing"), message: t("admin.tryAgain") });
      });
    return () => {
      cancelled = true;
    };
  }, [cacheScope, t]);

  const pricingMap = useMemo(() => {
    const map = {};
    for (const row of pricing) {
      map[row.service_area_id] = row.price;
    }
    return map;
  }, [pricing]);

  const dirty = useMemo(
    () => [...selectedIds].sort().join() !== [...savedIds].sort().join(),
    [selectedIds, savedIds]
  );

  useEffect(() => {
    if (!locationOpen) return undefined;
    const overflow = document.body.style.overflow;
    const escape = (event) => {
      if (event.key === "Escape" && !creating) setLocationOpen(false);
    };
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", escape);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", escape);
    };
  }, [creating, locationOpen]);

  useEffect(() => {
    if (!dirty && !pricingDirty) return undefined;
    const warn = (event) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty, pricingDirty]);

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    return areas.filter(
      (area) => !query || `${area.name_en} ${area.name_ar} ${area.code}`.toLowerCase().includes(query)
    );
  }, [areas, search]);

  const toggle = (id) =>
    setSelectedIds((current) =>
      current.includes(id) ? current.filter((value) => value !== id) : [...current, id]
    );

  const updateAreaPrice = (areaId, priceStr) => {
    const num = priceStr === "" ? null : parseFloat(priceStr);
    if (priceStr !== "" && (isNaN(num) || num < 0)) return;
    setPricing((prev) => {
      const next = prev.filter((r) => r.service_area_id !== areaId);
      if (num !== null) {
        next.push({ id: `pending-${areaId}`, service_area_id: areaId, price: num });
      }
      return next;
    });
    setPricingDirty(true);
  };

  const createLocation = async (event) => {
    event.preventDefault();
    if (creating) return;
    setCreating(true);
    setLocationError("");
    try {
      const result = await createEcommerceDeliveryLocation(
        {
          country: location.country.trim(),
          levels: location.levels
            .map((level, index) => level.trim() || location.levels_ar[index].trim())
            .filter(Boolean),
          name_ar:
            location.country_ar.trim() || location.levels_ar.some((level) => level.trim())
              ? [
                  location.country_ar.trim() || location.country.trim(),
                  ...location.levels
                    .map((level, index) => location.levels_ar[index].trim() || level.trim())
                    .filter(Boolean),
                ].join(" / ")
              : "",
        },
        { scope: cacheScope }
      );
      if (!result?.area?.id) throw new Error(t("admin.saveDeliveryError"));
      setAreas((current) => [...current, result.area]);
      setSelectedIds((current) => [...current, result.area.id]);
      setSearch("");
      setLocationOpen(false);
      setToast({
        type: "success",
        title: t("feedback.locationCreated"),
        message: t("feedback.locationCreatedBody"),
      });
    } catch {
      setLocationError(t("admin.saveDeliveryError"));
      setToast({ type: "error", title: t("admin.saveDeliveryError"), message: t("admin.tryAgain") });
    } finally {
      setCreating(false);
    }
  };

  const deleteLocation = async (area) => {
    if (deletingId) return;
    setDeletingId(area.id);
    try {
      await deleteEcommerceDeliveryLocation(area.id, { scope: cacheScope });
      setAreas((current) => current.filter((item) => item.id !== area.id));
      setSelectedIds((current) => current.filter((id) => id !== area.id));
      setSavedIds((current) => current.filter((id) => id !== area.id));
      setPricing((current) => current.filter((row) => row.service_area_id !== area.id));
      setToast({ type: "success", title: t("merchant.locationDeleted"), message: t("merchant.locationDeletedBody") });
    } catch {
      setToast({ type: "error", title: t("merchant.deleteLocationError"), message: t("admin.tryAgain") });
    } finally {
      setDeletingId("");
    }
  };

  const save = async () => {
    setSaving(true);
    try {
      await saveEcommerceDeliveryAreas(selectedIds, { scope: cacheScope });
      setSavedIds(selectedIds);
      if (pricingDirty || dirty) {
        const pricesByArea = new Map(
          pricing.map((row) => [row.service_area_id, row.price]),
        );
        const toSave = selectedIds.map((serviceAreaId) => ({
          service_area_id: serviceAreaId,
          price: Number(pricesByArea.get(serviceAreaId) ?? 0),
        }));
        try {
          await saveEcommerceDeliveryPricing(toSave, { scope: cacheScope });
        } catch {
          setToast({ type: "error", title: t("merchant.savePricingError"), message: t("admin.tryAgain") });
          return;
        }
        setPricingDirty(false);
      }
      setToast({
        type: "success",
        title: pricingDirty ? t("admin.pricingSaved") : t("admin.deliverySaved"),
        message: pricingDirty
          ? t("admin.pricingSavedBody")
          : t("admin.deliverySavedBody", { count: selectedIds.length }),
      });
    } catch {
      setToast({ type: "error", title: t("admin.saveDeliveryError"), message: t("admin.tryAgain") });
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="ecommerce-page ecommerce-operations-page ecommerce-delivery-page" dir={direction} lang={locale}>
      {loading ? (
        <PageHeaderSkeleton className="ecommerce-page-header app-page-intro" />
      ) : (
        <header className="ecommerce-page-header app-page-intro">
          <div>
            <h1>{t("merchant.deliveryTitle")}</h1>
            <p>{t("merchant.deliverySubtitle")}</p>
          </div>
        </header>
      )}
      {!loading && (
        <div className="ecommerce-page-actions ecommerce-delivery-actions">
          <button
            type="button"
            className="ecommerce-primary-button"
            disabled={loading || saving}
            onClick={() => {
              setLocation({ country: "", country_ar: "", levels: ["", ""], levels_ar: ["", ""] });
              setLocationError("");
              setLocationOpen(true);
            }}
          >
            <Plus size={18} />
            {t("merchant.addCustomLocation")}
          </button>
          <button
            type="button"
            className="ecommerce-primary-button"
            disabled={loading || saving || (!dirty && !pricingDirty)}
            onClick={save}
          >
            {saving ? <LoaderCircle className="is-spinning" size={18} /> : <Save size={18} />}
            {saving ? t("merchant.saving") : t("merchant.saveDelivery")}
          </button>
        </div>
      )}

      <section className="ecommerce-operations-card">
        <div className="ecommerce-operations-toolbar">
          <label className="ecommerce-search">
            <Search size={17} />
            <input
              aria-label={t("merchant.searchAreas")}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t("merchant.searchAreas")}
            />
          </label>
          <span className="ecommerce-delivery-enabled-count">{t("merchant.enabledCount", { count: selectedIds.length })}</span>
        </div>
        {loading ? (
          <EcommerceOperationsSkeleton variant="delivery" label={t("admin.loadingDelivery")} />
        ) : (
          <div className="ecommerce-delivery-grid">
            {visible.map((area) => (
              <div key={area.id} className={"ecommerce-delivery-card" + (selectedIds.includes(area.id) ? " is-enabled" : "")}>
                <div className="ecommerce-delivery-card-header">
                  <input
                    className="ecommerce-delivery-card-toggle"
                    type="checkbox"
                    aria-label={locale === "ar" ? area.name_ar || area.name_en : area.name_en || area.name_ar}
                    checked={selectedIds.includes(area.id)}
                    onChange={() => toggle(area.id)}
                    onClick={(event) => event.stopPropagation()}
                  />
                  <span className="ecommerce-delivery-card-title" onClick={() => toggle(area.id)} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(area.id); } }}>
                    <MapPin size={18} aria-hidden="true" />
                    <span className="ecommerce-delivery-area-name">
                      {locale === "ar" ? area.name_ar || area.name_en : area.name_en || area.name_ar}
                    </span>
                  </span>
                  <span className="ecommerce-delivery-card-actions">
                    {area.code?.startsWith("custom-") && (
                      <button type="button" disabled={deletingId === area.id} className="ecommerce-delivery-card-delete" aria-label={t("admin.delete", { name: area.name_en })} onClick={(e) => { e.stopPropagation(); deleteLocation(area); }}>
                        {deletingId === area.id ? <LoaderCircle className="is-spinning" size={15} /> : <Trash2 size={15} />}
                      </button>
                    )}
                  </span>
                </div>
                <div className="ecommerce-delivery-card-fee">
                  <span className="ecommerce-delivery-fee-label">{t("merchant.deliveryFee")}</span>
                  <div className="ecommerce-delivery-price-field">
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      disabled={!selectedIds.includes(area.id)}
                      className="ecommerce-delivery-price-input"
                      value={pricingMap[area.id] ?? ""}
                      onChange={(event) => updateAreaPrice(area.id, event.target.value)}
                      onClick={(e) => e.stopPropagation()}
                      placeholder="0.00"
                      aria-label={`${t("merchant.deliveryPrice")} — ${area.name_en || area.name_ar}`}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
        {!loading && !areas.length && <div className="ecommerce-operations-state">{t("admin.noDeliveryAreas")}</div>}
      </section>

      {locationOpen && (
        <div
          className="ecommerce-product-editor-modal-backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !creating) setLocationOpen(false);
          }}
        >
          <section className="ecommerce-delivery-location-dialog" role="dialog" aria-modal="true" aria-labelledby="custom-location-title">
            <header>
              <h2 id="custom-location-title">{t("merchant.addCustomLocation")}</h2>
              <button type="button" disabled={creating} aria-label={t("admin.close")} onClick={() => setLocationOpen(false)}>
                <X size={20} />
              </button>
            </header>
            <form onSubmit={createLocation}>
              <div className="ecommerce-location-language-head">
                <span>{t("merchant.locationDetails")}</span>
                <span>{t("merchant.locationArabicLanguage")}</span>
              </div>
              <div className="ecommerce-location-language-pair">
                <label>
                  {t("merchant.locationCountry")}
                  <input
                    aria-label={t("merchant.locationCountry")}
                    autoFocus
                    required
                    maxLength={100}
                    disabled={creating}
                    value={location.country}
                    placeholder={t("merchant.locationCountryExample")}
                    onChange={(event) => setLocation((current) => ({ ...current, country: event.target.value }))}
                  />
                </label>
                <label>
                  {t("merchant.locationCountry")}
                  <input
                    aria-label={t("merchant.locationCountryArabic")}
                    dir="rtl"
                    maxLength={100}
                    disabled={creating}
                    value={location.country_ar}
                    onChange={(event) => setLocation((current) => ({ ...current, country_ar: event.target.value }))}
                  />
                </label>
              </div>
              {location.levels.map((level, index) => (
                <div className="ecommerce-location-level-field" key={index}>
                  <div className="ecommerce-location-language-pair">
                    <label>
                      {t(index === 0 ? "merchant.locationRegionShort" : index === 1 ? "merchant.locationCityShort" : "merchant.locationOtherShort")}
                      <input
                        aria-label={t(index === 0 ? "merchant.locationRegion" : index === 1 ? "merchant.locationCity" : "merchant.locationOther")}
                        maxLength={100}
                        disabled={creating}
                        value={level}
                        onChange={(event) =>
                          setLocation((current) => ({
                            ...current,
                            levels: current.levels.map((value, position) => (position === index ? event.target.value : value)),
                          }))
                        }
                      />
                    </label>
                    <label>
                      {t(index === 0 ? "merchant.locationRegionShort" : index === 1 ? "merchant.locationCityShort" : "merchant.locationOtherShort")}
                      <input
                        aria-label={t(index === 0 ? "merchant.locationRegionArabic" : index === 1 ? "merchant.locationCityArabic" : "merchant.locationOtherArabic")}
                        dir="rtl"
                        maxLength={100}
                        disabled={creating}
                        value={location.levels_ar[index]}
                        onChange={(event) =>
                          setLocation((current) => ({
                            ...current,
                            levels_ar: current.levels_ar.map((value, position) => (position === index ? event.target.value : value)),
                          }))
                        }
                      />
                    </label>
                  </div>
                  {index >= 2 && (
                    <button
                      type="button"
                      disabled={creating}
                      aria-label={t("merchant.removeLocationLevel", { number: index + 1 })}
                      onClick={() =>
                        setLocation((current) => ({
                          ...current,
                          levels: current.levels.filter((_, position) => position !== index),
                          levels_ar: current.levels_ar.filter((_, position) => position !== index),
                        }))
                      }
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
              ))}
              <button
                type="button"
                className="ecommerce-secondary-button"
                disabled={creating || location.levels.length >= 5}
                onClick={() =>
                  setLocation((current) => ({
                    ...current,
                    levels: [...current.levels, ""],
                    levels_ar: [...current.levels_ar, ""],
                  }))
                }
              >
                <Plus size={16} />
                {t("merchant.addLocationLevel")}
              </button>
              {locationError && <p>{locationError}</p>}
              <footer>
                <button type="button" className="ecommerce-secondary-button" disabled={creating} onClick={() => setLocationOpen(false)}>
                  {t("common.cancel")}
                </button>
                <button type="submit" className="ecommerce-primary-button" disabled={creating || !location.country.trim()}>
                  {creating ? <LoaderCircle className="is-spinning" size={17} /> : <Plus size={17} />}
                  {t("merchant.addLocation")}
                </button>
              </footer>
            </form>
          </section>
        </div>
      )}

      <AuthToast dir={direction} key={toast?.id} type={toast?.type} title={toast?.title} message={toast?.message} onDismiss={() => setToast(null)} />
    </main>
  );
}
