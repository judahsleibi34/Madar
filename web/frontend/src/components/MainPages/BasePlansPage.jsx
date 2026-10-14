import { useEffect, useMemo, useState } from "react";
import { Bot, CheckCircle2, LockKeyhole, PackageCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { getPricingContent } from "../../content";
import { DASHBOARD_ROUTES } from "../../config/routes";
import { BILLING_API_ROUTES } from "../../services/apiRoutes";
import { apiFetch, getApiUrl } from "../../utils/apiClient";

const MODULE_IDS = ["forms", "website", "ecommerce"];

const formatPrice = (minor, currency, lang) =>
  new Intl.NumberFormat(lang === "ar" ? "ar" : "en-US", {
    style: "currency", currency: currency || "USD", maximumFractionDigits: 0,
  }).format(Number(minor) / 100);

const isMinorAmount = (value) => Number.isInteger(value) && value > 0;

// Classifies the backend response; it never substitutes prices of its own.
// eslint-disable-next-line react-refresh/only-export-components
export const readPriceBook = (catalog, failed) => {
  if (failed) return { book: null, unavailable: "backend" };
  if (!catalog || typeof catalog !== "object") return { book: null, unavailable: "malformed" };
  if (!("price_book" in catalog)) return { book: null, unavailable: "incompatible" };
  const book = catalog.price_book;
  if (book === null) return { book: null, unavailable: "bookUnavailable" };
  const valid = typeof book === "object"
    && MODULE_IDS.every((id) => isMinorAmount(book.standalone_minor?.[id]))
    && isMinorAmount(book.bundle_minor?.["2"])
    && isMinorAmount(book.bundle_minor?.["3"])
    && typeof book.new_sales_active === "boolean";
  return valid ? { book, unavailable: null } : { book: null, unavailable: "malformed" };
};

// Savings are display-only comparisons between amounts the price book already
// states; the price of any subscription still comes from the server quote.
// eslint-disable-next-line react-refresh/only-export-components
export const bundleSavings = (standalone, bundles) => {
  const pairs = MODULE_IDS.flatMap((a, index) => MODULE_IDS.slice(index + 1).map((b) => standalone[a] + standalone[b]));
  const pairSavings = pairs.map((separate) => separate - bundles["2"]);
  const allSeparate = MODULE_IDS.reduce((total, id) => total + standalone[id], 0);
  return [
    { id: "two", size: 2, price: bundles["2"], minSaving: Math.min(...pairSavings), maxSaving: Math.max(...pairSavings) },
    { id: "three", size: 3, price: bundles["3"], minSaving: allSeparate - bundles["3"], maxSaving: allSeparate - bundles["3"] },
  ].filter((bundle) => bundle.minSaving > 0);
};

export default function BasePlansPage({ lang = "en" }) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const t = getPricingContent(activeLang);
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    apiFetch(getApiUrl(BILLING_API_ROUTES.catalog), { method: "GET", cache: "no-store" })
      .then(async (response) => {
        const data = await response.json().catch(() => null);
        if (!response.ok || !data) throw new Error("catalog_unavailable");
        if (!cancelled) setCatalog(data.catalog ?? null);
      })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const modules = useMemo(() => {
    const products = catalog?.products || [];
    return MODULE_IDS.map((id) => products.find((product) => product.id === id)).filter(Boolean);
  }, [catalog]);
  const { book, unavailable } = readPriceBook(catalog, error);
  const assistant = (catalog?.products || []).find((product) => product.id === "ai_website_assistant"
    && product.type === "add_on" && isMinorAmount(product.price_minor));
  const status = !book ? null
    : book.new_sales_active ? "open"
    : book.sales_end_at && new Date(book.sales_end_at) <= new Date() ? "closed"
    : "prepared";
  const currency = book?.currency || catalog?.currency || "USD";
  const bundleCards = book ? bundleSavings(book.standalone_minor, book.bundle_minor).map((bundle) => ({
    ...bundle, name: bundle.size === 2 ? t.anyTwo : t.allThree,
  })) : [];
  const money = (minor) => formatPrice(minor, currency, activeLang);
  const savingsText = (bundle) => (bundle.minSaving === bundle.maxSaving
    ? t.bundleSavingsExact.replace("{amount}", money(bundle.minSaving))
    : t.bundleSavingsRange.replace("{min}", money(bundle.minSaving)).replace("{max}", money(bundle.maxSaving)));

  const priceRow = (minor) => <div className="pricing-catalog-price"><strong>{money(minor)}</strong><span>{t.perMonth}</span></div>;

  return (
    <main className="pricing-page launch-pricing" dir={activeLang === "ar" ? "rtl" : "ltr"}>
      <header className="pricing-inner-header app-page-intro"><div className="pricing-section-heading"><h1>{t.title}</h1><p>{t.subtitle}</p></div></header>
      <section className="pricing-base-section">
        {loading && <div className="launch-pricing-notice" role="status">{t.loading}</div>}
        {!loading && unavailable && <div className="launch-pricing-notice" role="alert"><strong>{t.unavailable[unavailable].title}</strong><p>{t.unavailable[unavailable].body}</p></div>}
        {!loading && book && <>
          <div className={`launch-pricing-notice launch-price-status is-${status}`} role="status"><LockKeyhole size={18} aria-hidden="true" /><div><strong>{t[status]}</strong><p>{t.statusHelp[status]}</p></div></div>

          <section className="launch-pricing-group" aria-labelledby="launch-modules-title">
            <div className="pricing-catalog-heading"><div><span>{t.modulesLabel}</span><h2 id="launch-modules-title">{t.modulesTitle}</h2></div></div>
            <div className="pricing-plan-strip pricing-comparison-grid launch-module-grid">{modules.map((module) => <article className="pricing-mini-plan pricing-catalog-plan" key={module.id}>
              <header className="pricing-catalog-plan-header">
                <div><span>{t.moduleLabel}</span><PackageCheck size={18} aria-hidden="true" /></div>
                <h3>{t.modules[module.id]?.name || module.name}</h3>
                <p>{t.modules[module.id]?.summary || module.summary}</p>
              </header>
              {priceRow(book.standalone_minor[module.id])}
              {module.id === "website" && <ul className="pricing-feature-list"><li className="included"><CheckCircle2 size={15} aria-hidden="true" /><span>{t.reservations}</span></li></ul>}
            </article>)}</div>
          </section>

          <section className="launch-pricing-group" aria-labelledby="launch-bundles-title">
            <div className="pricing-catalog-heading"><div><span>{t.bundlesLabel}</span><h2 id="launch-bundles-title">{t.bundlesTitle}</h2></div></div>
            <div className="pricing-plan-strip pricing-comparison-grid launch-bundle-grid">{bundleCards.map((bundle) => <article className="pricing-mini-plan pricing-catalog-plan launch-bundle-card" key={bundle.id}>
              <header className="pricing-catalog-plan-header">
                <div><span>{t.bundleLabel}</span></div>
                <h3>{bundle.name}</h3>
              </header>
              {priceRow(bundle.price)}
              <ul className="pricing-feature-list"><li className="included"><CheckCircle2 size={15} aria-hidden="true" /><span>{savingsText(bundle)}</span></li></ul>
            </article>)}</div>
          </section>

          {assistant && <section className="launch-pricing-group" aria-labelledby="launch-addons-title">
            <div className="pricing-catalog-heading"><div><span>{t.addonsLabel}</span><h2 id="launch-addons-title">{t.addonsTitle}</h2></div></div>
            <article className="pricing-mini-plan pricing-catalog-plan launch-addon-card">
              <div className="launch-addon-main">
                <div className="launch-addon-icon"><Bot size={26} aria-hidden="true" /></div>
                <div>
                  <div className="launch-addon-tags"><span>{t.addonLabel}</span>{assistant.coming_soon && <em>{t.comingSoon}</em>}</div>
                  <h3>{t.assistant.name}</h3>
                  <p>{t.assistant.summary}</p>
                  <ul className="pricing-feature-list">{t.assistant.points.map((point) => <li className="included" key={point}><CheckCircle2 size={15} aria-hidden="true" /><span>{point}</span></li>)}</ul>
                </div>
              </div>
              <div className="launch-addon-price">
                <span>{t.addToAnyPlan}</span>
                <div className="pricing-catalog-price"><strong>+{formatPrice(assistant.price_minor, assistant.currency || currency, activeLang)}</strong><span>{t.perMonth}</span></div>
                <ul className="launch-addon-modules" aria-label={t.worksWith}>{MODULE_IDS.map((id) => <li key={id}>{t.modules[id].name}</li>)}</ul>
              </div>
            </article>
          </section>}

          <section className="launch-pricing-group launch-terms" aria-labelledby="launch-terms-title">
            <div className="pricing-catalog-heading"><div><span>{t.termsLabel}</span><h2 id="launch-terms-title">{t.termsTitle}</h2></div></div>
            <ul className="pricing-feature-list">{t.terms.map((term) => <li className="included" key={term}><CheckCircle2 size={15} aria-hidden="true" /><span>{term}</span></li>)}</ul>
            <p>{t.reviewed}</p>
            <button type="button" className={`pricing-plan-button ${book.new_sales_active ? "primary" : "secondary"}`} disabled={!book.new_sales_active} onClick={() => navigate(DASHBOARD_ROUTES.myPlan)}>{book.new_sales_active ? t.manage : t.unavailableAction}</button>
          </section>
        </>}
      </section>
    </main>
  );
}
