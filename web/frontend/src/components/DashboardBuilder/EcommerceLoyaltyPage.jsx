import { useEffect, useMemo, useState } from "react";
import { Gift, LoaderCircle, Save } from "lucide-react";

import AuthToast from "../AuthPages/AuthToast";
import { fetchEcommerceCatalog, fetchEcommerceLoyalty, saveEcommerceLoyalty } from "../../services/ecommerceApi";
import { useCommerceI18n } from "../../utils/commerceI18n";

const EMPTY = {
  enabled: false,
  earning_rate_basis_points: 500,
  threshold_points: 100,
  reward_product_id: "",
  reward_discount_basis_points: 1000,
  validity_mode: "lifetime",
  validity_days: "",
};

export default function EcommerceLoyaltyPage() {
  const { t, locale, direction, localize } = useCommerceI18n();
  const [form, setForm] = useState(EMPTY);
  const [saved, setSaved] = useState(EMPTY);
  const [products, setProducts] = useState([]);
  const [currency, setCurrency] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchEcommerceLoyalty(), fetchEcommerceCatalog()])
      .then(([loyalty, catalog]) => {
        if (cancelled) return;
        const next = loyalty?.rule ? {
          ...EMPTY,
          ...loyalty.rule,
          validity_days: loyalty.rule.validity_days ?? "",
        } : EMPTY;
        setForm(next);
        setSaved(next);
        setCurrency(loyalty?.currency || "");
        setProducts((catalog?.products || []).filter((product) => ["active", "inactive"].includes(product.status)));
      })
      .catch((error) => setToast({ type: "error", title: t("loyalty.loadError"), message: error.message }))
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [t]);

  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(saved), [form, saved]);
  useEffect(() => {
    if (!dirty) return undefined;
    const warn = (event) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const update = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const save = async () => {
    setSaving(true);
    try {
      const payload = {
        enabled: Boolean(form.enabled),
        earning_rate_basis_points: Number(form.earning_rate_basis_points),
        threshold_points: Number(form.threshold_points),
        reward_product_id: form.reward_product_id,
        validity_mode: form.validity_mode,
        validity_days: form.validity_mode === "fixed_period" ? Number(form.validity_days) : null,
      };
      const result = await saveEcommerceLoyalty(payload);
      const next = { ...EMPTY, ...result.rule, validity_days: result.rule.validity_days ?? "" };
      setForm(next);
      setSaved(next);
      setToast({ type: "success", title: t("loyalty.saved"), message: t("loyalty.savedBody") });
    } catch (error) {
      setToast({ type: "error", title: t("loyalty.saveError"), message: error.message });
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="ecommerce-page ecommerce-operations-page" dir={direction} lang={locale}>
      <header className="ecommerce-page-header app-page-intro">
        <div><h1>{t("loyalty.title")}</h1><p>{t("loyalty.subtitle")}</p></div>
        <button type="button" className="ecommerce-primary-button" disabled={loading || saving || !dirty || !form.reward_product_id} onClick={save}>
          {saving ? <LoaderCircle className="is-spinning" size={18} /> : <Save size={18} />}{saving ? t("merchant.saving") : t("common.save")}
        </button>
      </header>
      <section className="ecommerce-operations-card">
        {loading ? <div className="ecommerce-operations-state"><LoaderCircle className="is-spinning" />{t("common.loading")}</div> : (
          <div className="ecommerce-form-grid">
            <label><span>{t("loyalty.enabled")}</span><input type="checkbox" checked={Boolean(form.enabled)} onChange={(event) => update("enabled", event.target.checked)} /></label>
            <label><span>{t("common.currency")}</span><input value={currency} readOnly /></label>
            <label><span>{t("loyalty.earningRate")}</span><input type="number" min="0.01" max="100" step="0.01" value={Number(form.earning_rate_basis_points) / 100} onChange={(event) => update("earning_rate_basis_points", Math.round(Number(event.target.value) * 100))} /></label>
            <label><span>{t("loyalty.threshold")}</span><input type="number" min="1" value={form.threshold_points} onChange={(event) => update("threshold_points", event.target.value)} /></label>
            <label><span>{t("loyalty.rewardProduct")}</span><select value={form.reward_product_id} onChange={(event) => update("reward_product_id", event.target.value)}><option value="">{t("loyalty.chooseProduct")}</option>{products.map((product) => <option key={product.id} value={product.id}>{localize(product.translations)}</option>)}</select></label>
            <label><span>{t("loyalty.discount")}</span><input value="10%" readOnly /></label>
            <label><span>{t("loyalty.validity")}</span><select value={form.validity_mode} onChange={(event) => update("validity_mode", event.target.value)}><option value="lifetime">{t("loyalty.lifetime")}</option><option value="fixed_period">{t("loyalty.fixedPeriod")}</option></select></label>
            {form.validity_mode === "fixed_period" && <label><span>{t("loyalty.validityDays")}</span><input type="number" min="1" max="3650" value={form.validity_days} onChange={(event) => update("validity_days", event.target.value)} /></label>}
          </div>
        )}
        <p className="ecommerce-operations-warning"><Gift size={17} aria-hidden="true" /> {t("loyalty.earningExplanation")}</p>
      </section>
      <AuthToast type={toast?.type} title={toast?.title} message={toast?.message} onDismiss={() => setToast(null)} />
    </main>
  );
}
