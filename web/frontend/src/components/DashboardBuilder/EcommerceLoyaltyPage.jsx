import PageHeaderSkeleton from "../common/PageHeaderSkeleton";
import { readEcommerceCatalogCacheSnapshot } from "./utils/ecommerceCatalogCache";
import { getEcommerceCacheScope, readEcommerceAdminCacheSnapshot } from "./utils/ecommerceAdminCache";
import { useEffect, useMemo, useState } from "react";
import { ArrowRight, ChevronDown, LoaderCircle, Plus, Save, Search, Trash2, X } from "lucide-react";

import EcommerceToast from "./EcommerceToast";
import EcommerceOperationsSkeleton from "./EcommerceOperationsSkeleton";
import { fetchEcommerceCatalog, fetchEcommerceLoyalty, saveEcommerceLoyalty, fetchEcommerceSettings, saveEcommerceSettings } from "../../services/ecommerceApi";
import { useCommerceI18n } from "../../utils/commerceI18n";

const newCondition = (audience = "loyalty") => ({
  audience, product_ids: [], discount_basis_points: audience === "loyalty" ? 1000 : 500,
  validity_mode: "lifetime", validity_days: null,
});
const normalizeRule = (rule) => ({
  enabled:rule?.enabled ?? true,
  earning_rate_basis_points:rule?.earning_rate_basis_points ?? 500,
  threshold_points:rule?.threshold_points ?? 100,
  discount_conditions:rule?.discount_conditions?.length ? rule.discount_conditions.map((condition) => ({ ...condition })) : [
    { ...newCondition(), product_ids:rule?.reward_product_id ? [rule.reward_product_id] : [],
      discount_basis_points:rule?.reward_discount_basis_points ?? 1000,
      validity_mode:rule?.validity_mode || "lifetime", validity_days:rule?.validity_days ?? null },
  ],
});

function ConditionCard({ condition, index, products, update, remove, t, localize }) {
  const [search, setSearch] = useState("");
  const choices = products.filter((product) => localize(product.translations).toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  const selectedProducts = condition.product_ids.map((id) => ({
    id,
    name:localize(products.find((product) => product.id === id)?.translations) || id,
  }));
  const allSelected = choices.length > 0 && choices.every((product) => condition.product_ids.includes(product.id));
  const selectAll = () => update("product_ids", [...new Set([...condition.product_ids, ...choices.map((product) => product.id)])].slice(0, 100));
  const toggle = (id) => update("product_ids", condition.product_ids.includes(id)
    ? condition.product_ids.filter((selected) => selected !== id) : [...condition.product_ids, id]);
  const audienceLabel = t(condition.audience === "loyalty" ? "loyalty.loyaltyAudienceShort" : "loyalty.normalAudienceShort");
  const discountPercent = Number(condition.discount_basis_points || 0) / 100;

  return (
    <section className="ecommerce-loyalty-condition" aria-label={t("loyalty.conditionNumber", { number:index + 1 })}>
      <header>
        <div className="ecommerce-loyalty-condition-heading">
          <span className="ecommerce-loyalty-condition-number" aria-hidden="true">{index + 1}</span>
          <div>
            <h2>{t("loyalty.conditionNumber", { number:index + 1 })}</h2>
            <p>{t("loyalty.conditionSummary", { audience:audienceLabel, discount:discountPercent, count:condition.product_ids.length })}</p>
          </div>
        </div>
        {remove && <button type="button" className="ecommerce-loyalty-remove" title={t("loyalty.removeCondition", { number:index + 1 })} aria-label={t("loyalty.removeCondition", { number:index + 1 })} onClick={remove}><Trash2 size={17} /></button>}
      </header>

      <div className="ecommerce-loyalty-condition-grid">
        <label>
          <span>{t("loyalty.audience")}</span>
          <select aria-label={t("loyalty.audience")} aria-describedby={"loyalty-audience-help-" + index} value={condition.audience} onChange={(event) => update("audience", event.target.value)}>
            <option value="loyalty">{t("loyalty.loyaltyAudience")}</option>
            <option value="normal">{t("loyalty.normalAudience")}</option>
          </select>
          <small id={"loyalty-audience-help-" + index}>{t(condition.audience === "loyalty" ? "loyalty.loyaltyAudienceHelp" : "loyalty.normalAudienceHelp")}</small>
        </label>
        <label>
          <span>{t("loyalty.discountPercent")}</span>
          <div className="ecommerce-loyalty-percent-input">
            <input aria-label={t("loyalty.discountPercent")} aria-describedby={"loyalty-discount-help-" + index} type="number" min="0.01" max="100" step="0.01" value={discountPercent} onChange={(event) => update("discount_basis_points", Math.round(Number(event.target.value) * 100))} />
            <span aria-hidden="true">%</span>
          </div>
          <small id={"loyalty-discount-help-" + index}>{t("loyalty.discountHelp")}</small>
        </label>
        <label>
          <span>{t("loyalty.validity")}</span>
          <select aria-label={t("loyalty.validity")} aria-describedby={"loyalty-validity-help-" + index} value={condition.validity_mode} onChange={(event) => {
            const mode = event.target.value;
            update("validity_mode", mode);
            update("validity_days", mode === "lifetime" ? null : condition.validity_days || 30);
          }}>
            <option value="lifetime">{t("loyalty.lifetime")}</option>
            <option value="fixed_period">{t("loyalty.fixedPeriod")}</option>
          </select>
          <small id={"loyalty-validity-help-" + index}>{t(condition.validity_mode === "lifetime" ? "loyalty.lifetimeHelp" : condition.audience === "normal" ? "loyalty.normalPeriodHint" : "loyalty.loyaltyPeriodHint")}</small>
        </label>
        {condition.validity_mode === "fixed_period" && <label>
          <span>{t("loyalty.validityDays")}</span>
          <input aria-label={t("loyalty.validityDays")} type="number" min="1" max="3650" value={condition.validity_days ?? ""} onChange={(event) => update("validity_days", Number(event.target.value))} />
        </label>}
      </div>

      <details className="ecommerce-loyalty-product-picker">
        <summary>
          <span className="ecommerce-loyalty-picker-copy">
            <strong>{t("loyalty.rewardProducts")}</strong>
            <small>{t("loyalty.rewardProductsHelp")}</small>
          </span>
          <span className="ecommerce-loyalty-selected-count">{t("loyalty.selectedProducts", { count:condition.product_ids.length })}</span>
          <ChevronDown className="ecommerce-loyalty-picker-chevron" size={18} aria-hidden="true" />
        </summary>
        <div className="ecommerce-loyalty-picker-body">
          <label className="ecommerce-search"><Search size={16} aria-hidden="true" /><input aria-label={t("loyalty.searchProducts")} value={search} placeholder={t("loyalty.searchProducts")} onChange={(event) => setSearch(event.target.value)} /></label>
          <div className="ecommerce-loyalty-selection-actions">
            <button type="button" className="ecommerce-secondary-button" disabled={!choices.length || allSelected || condition.product_ids.length >= 100} onClick={selectAll}>{t(search.trim() ? "loyalty.selectAllResults" : "loyalty.selectAll")}</button>
            <button type="button" className="ecommerce-secondary-button" disabled={!condition.product_ids.length} onClick={() => update("product_ids", [])}>{t("loyalty.clearSelection")}</button>
          </div>
          <div className="ecommerce-loyalty-product-choices">
            {choices.map((product) => <label key={product.id} className={condition.product_ids.includes(product.id) ? "is-selected" : ""}><input type="checkbox" checked={condition.product_ids.includes(product.id)} disabled={!condition.product_ids.includes(product.id) && condition.product_ids.length >= 100} onChange={() => toggle(product.id)} /><span>{localize(product.translations)}</span></label>)}
            {!choices.length && <p>{t("loyalty.noProducts")}</p>}
          </div>
        </div>
      </details>

      {selectedProducts.length > 0 && <div className="ecommerce-loyalty-selected-products" aria-label={t("loyalty.selectedProducts", { count:selectedProducts.length })}>
        {selectedProducts.map((product) => <span key={product.id}>
          <span>{product.name}</span>
          <button type="button" aria-label={t("loyalty.removeProduct", { name:product.name })} title={t("loyalty.removeProduct", { name:product.name })} onClick={() => toggle(product.id)}><X size={13} /></button>
        </span>)}
      </div>}
    </section>
  );
}
export default function EcommerceLoyaltyPage({ user }) {
  const cacheScope = getEcommerceCacheScope(user);
  const { t, locale, direction, localize } = useCommerceI18n();
  const ruleSnapshot = readEcommerceAdminCacheSnapshot(cacheScope, "loyalty");
  const catalogSnapshot = readEcommerceCatalogCacheSnapshot(cacheScope);
  const settingsSnapshot = readEcommerceAdminCacheSnapshot(cacheScope, "settings");
  const initialRule = normalizeRule(ruleSnapshot?.data?.rule);
  const initialCurrency = settingsSnapshot?.data?.currency || ruleSnapshot?.data?.currency || catalogSnapshot?.catalog?.commerce_currency || "";
  const [form, setForm] = useState(() => initialRule);
  const [saved, setSaved] = useState(() => initialRule);
  const [products, setProducts] = useState(() => (catalogSnapshot?.catalog?.products || []).filter(product => ["active", "inactive"].includes(product.status)));
  const [currency, setCurrency] = useState(() => initialCurrency);
  const [savedCurrency, setSavedCurrency] = useState(() => initialCurrency);
  const [currencyLocked, setCurrencyLocked] = useState(() => !settingsSnapshot || Boolean(settingsSnapshot.data.currency_locked));
  const [loading, setLoading] = useState(() => !(ruleSnapshot && catalogSnapshot && settingsSnapshot));
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState(null);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const ruleSnapshot = readEcommerceAdminCacheSnapshot(cacheScope, "loyalty");
    const catalogSnapshot = readEcommerceCatalogCacheSnapshot(cacheScope);
    const settingsSnapshot = readEcommerceAdminCacheSnapshot(cacheScope, "settings");
    Promise.allSettled([fetchEcommerceLoyalty({ scope:cacheScope }), fetchEcommerceCatalog({ scope:cacheScope }), fetchEcommerceSettings({ scope:cacheScope })])
      .then(([loyaltyResult, catalogResult, settingsResult]) => {
        if (cancelled) return;
        const loyalty = loyaltyResult.status === "fulfilled" ? loyaltyResult.value : ruleSnapshot?.data;
        const catalog = catalogResult.status === "fulfilled" ? catalogResult.value : catalogSnapshot?.catalog;
        if (loyaltyResult.status === "rejected") { if (!ruleSnapshot) setLoadError(t("loyalty.loadError")); setToast({ type: "error", title: t("loyalty.loadError"), message: t("admin.tryAgain") }); }
        if (catalogResult.status === "rejected") setToast({ type:"error", title:t("loyalty.loadError"), message:t("admin.tryAgain") });
        const next = normalizeRule(loyalty?.rule);
        setForm(current => JSON.stringify(current) === JSON.stringify(normalizeRule(ruleSnapshot?.data?.rule)) ? { ...next, enabled:true } : current); setSaved(next);
        const settings = settingsResult.status === "fulfilled" ? settingsResult.value : settingsSnapshot?.data;
        const nextCurrency = settings?.currency || loyalty?.currency || catalog?.commerce_currency || "";
        const previousCurrency = settingsSnapshot?.data?.currency || ruleSnapshot?.data?.currency || catalogSnapshot?.catalog?.commerce_currency || "";
        setCurrency(current => current === previousCurrency ? nextCurrency : current); setSavedCurrency(nextCurrency);
        setCurrencyLocked(!settings || Boolean(settings.currency_locked));
        setProducts((catalog?.products || []).filter((product) => ["active", "inactive"].includes(product.status)));
      }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [cacheScope, t]);

  const earningRatePercent = form.earning_rate_basis_points === "" ? 0 : Number(form.earning_rate_basis_points) / 100;
  const mappingOrderTotal = 100;
  const mappedPoints = Math.floor((mappingOrderTotal * Math.max(0, Number(form.earning_rate_basis_points) || 0)) / 10000);
  const formattedMappingAmount = new Intl.NumberFormat(locale, { maximumFractionDigits:2 }).format(mappingOrderTotal);
  const formattedMappedPoints = new Intl.NumberFormat(locale, { maximumFractionDigits:0 }).format(mappedPoints);
  const formattedThreshold = new Intl.NumberFormat(locale, { maximumFractionDigits:0 }).format(Math.max(0, Number(form.threshold_points) || 0));
  const mappingCurrency = currency || t("loyalty.storeCurrency");

  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(saved) || currency !== savedCurrency, [form, saved, currency, savedCurrency]);
  const valid = form.threshold_points >= 1 && form.earning_rate_basis_points >= 1 && form.earning_rate_basis_points <= 10000
    && form.discount_conditions.some((condition) => condition.audience === "loyalty")
    && form.discount_conditions.every((condition) => condition.product_ids.length > 0 && condition.discount_basis_points >= 1
      && condition.discount_basis_points <= 10000 && (condition.validity_mode === "lifetime" || (condition.validity_days >= 1 && condition.validity_days <= 3650)));
  useEffect(() => {
    if (!dirty) return undefined;
    const warn = (event) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  const update = (key, value) => setForm((current) => ({ ...current, [key]:value }));
  const updateCondition = (index, key, value) => setForm((current) => ({
    ...current, discount_conditions:current.discount_conditions.map((condition, position) => position === index ? { ...condition, [key]:value } : condition),
  }));
  const save = async () => {
    setSaving(true);
    try {
      if (currency !== savedCurrency) {
        const settings = await saveEcommerceSettings(currency);
        const nextCurrency = settings?.currency || currency;
        setCurrency(nextCurrency); setSavedCurrency(nextCurrency);
        setCurrencyLocked(Boolean(settings?.currency_locked));
      }
      const result = await saveEcommerceLoyalty({ ...form, enabled:true, earning_rate_basis_points:Number(form.earning_rate_basis_points), threshold_points:Number(form.threshold_points) }, { scope:cacheScope });
      const next = normalizeRule(result.rule);
      setForm(next); setSaved(next);
      setToast({ type:"success", title:t("loyalty.saved"), message:t("loyalty.savedBody") });
    } catch {
      setToast({ type:"error", title:t("loyalty.saveError"), message:t("admin.tryAgain") });
    } finally { setSaving(false); }
  };

  return (
    <main className="ecommerce-page ecommerce-operations-page ecommerce-loyalty-page" dir={direction} lang={locale}>
      {(loading) ? <PageHeaderSkeleton className="ecommerce-page-header app-page-intro" /> : (<header className="ecommerce-page-header app-page-intro"><div><h1>{t("loyalty.title")}</h1><p>{t("loyalty.subtitle")}</p></div></header>)}
      <section className="ecommerce-operations-card">
        {loading ? <EcommerceOperationsSkeleton variant="loyalty" label={t("common.loading")} /> : <>
          <div className="ecommerce-form-grid">
            <label><span>{t("common.currency")}</span><select aria-label={t("common.currency")} value={currency} disabled={currencyLocked || saving} onChange={(event) => setCurrency(event.target.value)}><option value="" disabled>{t("loyalty.selectCurrency")}</option>{["ILS", "JOD", "USD", "EUR"].map((code) => <option key={code} value={code}>{code}</option>)}</select><small>{t(currencyLocked ? "loyalty.currencyLocked" : "loyalty.currencyHelp")}</small></label>
            <label>
              <span>{t("loyalty.earningRate")}</span>
              <input aria-label={t("loyalty.earningRate")} aria-describedby="loyalty-earning-rate-help" type="number" min="0.01" max="100" step="0.01" value={form.earning_rate_basis_points === "" ? "" : earningRatePercent} onChange={(event) => update("earning_rate_basis_points", event.target.value === "" ? "" : Math.round(Number(event.target.value) * 100))} />
              <small id="loyalty-earning-rate-help">{t("loyalty.earningRateHelp")}</small>
            </label>
            <label>
              <span>{t("loyalty.threshold")}</span>
              <input aria-label={t("loyalty.threshold")} aria-describedby="loyalty-threshold-help" type="number" min="1" max="10000000000" step="1" value={form.threshold_points} onChange={(event) => update("threshold_points", event.target.value)} />
              <small id="loyalty-threshold-help">{t("loyalty.thresholdHelp")}</small>
            </label>
          </div>
          <section className="ecommerce-loyalty-points-map" aria-labelledby="loyalty-points-map-title" aria-live="polite">
            <header>
              <h2 id="loyalty-points-map-title">{t("loyalty.pointsMappingTitle")}</h2>
              <p>{t("loyalty.pointsMappingHelp")}</p>
            </header>
            <div className="ecommerce-loyalty-points-flow">
              <article><span>1</span><strong>{t("loyalty.orderValue")}</strong><p>{t("loyalty.mappingOrder", { amount:formattedMappingAmount, currency:mappingCurrency })}</p></article>
              <ArrowRight size={20} aria-hidden="true" />
              <article><span>2</span><strong>{t("loyalty.pointsEarned")}</strong><p>{t("loyalty.mappingEarns", { points:formattedMappedPoints })}</p></article>
              <ArrowRight size={20} aria-hidden="true" />
              <article><span>3</span><strong>{t("loyalty.rewardUnlock")}</strong><p>{t("loyalty.mappingThreshold", { points:formattedThreshold })}</p></article>
            </div>
            <p className="ecommerce-loyalty-points-note">{t("loyalty.earningExplanation")}</p>
          </section>
          <div className="ecommerce-loyalty-conditions-header"><h2>{t("loyalty.conditions")}</h2><p>{t("loyalty.highestDiscount")}</p></div>
          <fieldset disabled={saving} className="ecommerce-loyalty-conditions">
            {form.discount_conditions.map((condition, index) => <ConditionCard key={index} condition={condition} index={index} products={products} t={t} localize={localize}
              update={(key, value) => updateCondition(index, key, value)}
              remove={form.discount_conditions.length > 1 ? () => update("discount_conditions", form.discount_conditions.filter((_, position) => position !== index)) : null} />)}
          </fieldset>
          <button type="button" className="ecommerce-secondary-button" disabled={saving || form.discount_conditions.length >= 10} onClick={() => update("discount_conditions", [...form.discount_conditions, newCondition("normal")])}><Plus size={17} />{t("loyalty.addCondition")}</button>
          <footer className="ecommerce-loyalty-actions">
            <button type="button" className="ecommerce-primary-button" disabled={Boolean(loadError) || saving || !dirty || !valid} aria-busy={saving} onClick={save}>
              {saving ? <LoaderCircle className="is-spinning" size={18} /> : <Save size={18} />}{saving ? t("merchant.saving") : t("common.save")}
            </button>
          </footer>
        </>}
      </section>
      <EcommerceToast dir={direction} type={toast?.type} title={toast?.title} message={toast?.message} onDismiss={() => setToast(null)} />
    </main>
  );
}
