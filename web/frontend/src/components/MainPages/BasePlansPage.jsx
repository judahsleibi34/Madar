import { useEffect, useState } from "react";
import { BarChart3, Bot, CheckCircle2, FileText, Globe, GraduationCap, ShoppingBag } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { getPricingContent } from "../../content";
import { publicPlanOffers } from "../../content/pages/publicPlanOffers";
import { DASHBOARD_ROUTES } from "../../config/routes";
import { BILLING_API_ROUTES } from "../../services/apiRoutes";
import { apiFetch, getApiUrl } from "../../utils/apiClient";

const MODULE_IDS = ["forms", "website", "ecommerce"];
const MODULE_ICONS = { forms: FileText, website: Globe, ecommerce: ShoppingBag, statistics: BarChart3, elearning: GraduationCap };

const formatPrice = (minor, currency, lang) =>
  new Intl.NumberFormat(lang === "ar" ? "ar" : "en-US", {
    style: "currency", currency: currency || "USD", maximumFractionDigits: 0,
  }).format(Number(minor) / 100);

const isMinorAmount = (value) => Number.isInteger(value) && value > 0;

export default function BasePlansPage({ lang = "en" }) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const t = getPricingContent(activeLang);
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch(getApiUrl(BILLING_API_ROUTES.catalog), { method: "GET", cache: "no-store" })
      .then(async (response) => {
        const data = await response.json().catch(() => null);
        if (!response.ok || !data) throw new Error("catalog_unavailable");
        if (!cancelled) setCatalog(data.catalog ?? null);
      })
      // The catalog enriches the optional assistant only. Public plans must
      // remain visible when billing is unavailable or has no active price book.
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const products = Array.isArray(catalog?.products) ? catalog.products : [];
  const assistant = products.find((product) => product?.id === "ai_website_assistant"
    && product.type === "add_on" && isMinorAmount(product.price_minor));
  const currency = publicPlanOffers.currency;
  const modules = publicPlanOffers.modules.map((offer) => ({
    ...offer, content: t.modules[offer.id] || t[offer.id], Icon: MODULE_ICONS[offer.id],
  }));
  const money = (minor) => formatPrice(minor, currency, activeLang);

  const priceRow = (minor, starting = true) => <div className="pricing-starting-price">{starting && <span className="pricing-starting-label">{t.startingFrom}</span>}<div className="pricing-catalog-price"><strong>{money(minor)}</strong><span>{t.perMonth}</span></div></div>;

  return (
    <main className="pricing-page launch-pricing" dir={activeLang === "ar" ? "rtl" : "ltr"}>
      <header className="pricing-inner-header app-page-intro"><div className="pricing-section-heading"><h1>{t.title}</h1><p>{t.subtitle}</p></div></header>
      <section className="pricing-base-section">
          <section className="launch-pricing-group" aria-labelledby="launch-modules-title">
            <div className="pricing-catalog-heading"><div><h2 id="launch-modules-title">{t.modulesTitle}</h2><p>{t.modulesDescription}</p></div></div>
            <div className="pricing-plan-strip pricing-comparison-grid launch-module-grid">{modules.map(({ id, content, Icon, startingMinor }) => <article className={`pricing-mini-plan pricing-catalog-plan launch-${id}-card`} key={id}>
              <header className="pricing-catalog-plan-header">
                <div><Icon size={20} aria-hidden="true" /></div>
                <h3>{content.name}</h3>
                <p>{content.summary}</p>
              </header>
              {priceRow(startingMinor)}
              <ul className="pricing-feature-list">{content.points.map((point) => <li className="included" key={point}><CheckCircle2 size={15} aria-hidden="true" /><span>{point}</span></li>)}</ul>
            </article>)}
            </div>
          </section>

          <section className="launch-pricing-group" aria-labelledby="launch-all-title">
            <div className="pricing-catalog-heading"><div><h2 id="launch-all-title">{t.allModulesTitle}</h2><p>{t.allModulesDescription}</p></div></div>
            <article className="pricing-mini-plan pricing-catalog-plan launch-all-card">
              <header className="pricing-catalog-plan-header"><h3>{t.allModulesName}</h3><p>{t.allModulesSummary}</p></header>
              {priceRow(publicPlanOffers.allModulesMinor, false)}
              <ul className="pricing-feature-list">{modules.map(({ content: { name } }) => <li className="included" key={name}><CheckCircle2 size={15} aria-hidden="true" /><span>{name}</span></li>)}</ul>
            </article>
          </section>

          {assistant && <section className="launch-pricing-group" aria-labelledby="launch-addons-title">
            <div className="pricing-catalog-heading"><div><h2 id="launch-addons-title">{t.addonsTitle}</h2></div></div>
            <article className="pricing-mini-plan pricing-catalog-plan launch-addon-card">
              <div className="launch-addon-main">
                <div className="launch-addon-icon"><Bot size={26} aria-hidden="true" /></div>
                <div>
                  <div className="launch-addon-tags">{assistant.coming_soon && <em>{t.comingSoon}</em>}</div>
                  <h3>{t.assistant.name}</h3>
                  <p>{t.assistant.summary}</p>
                  <ul className="pricing-feature-list">{t.assistant.points.map((point) => <li className="included" key={point}><CheckCircle2 size={15} aria-hidden="true" /><span>{point}</span></li>)}</ul>
                </div>
              </div>
              <div className="launch-addon-price">
                <span>{t.addToAnyPlan}</span>
                <span className="pricing-starting-label">{t.startingFrom}</span>
                <div className="pricing-catalog-price"><strong>+{formatPrice(assistant.price_minor, assistant.currency || currency, activeLang)}</strong><span>{t.perMonth}</span></div>
                <ul className="launch-addon-modules" aria-label={t.worksWith}>{MODULE_IDS.map((id) => <li key={id}>{t.modules[id].name}</li>)}</ul>
              </div>
            </article>
          </section>}

          <section className="launch-pricing-group launch-terms" aria-labelledby="launch-terms-title">
            <div className="pricing-catalog-heading"><div><h2 id="launch-terms-title">{t.termsTitle}</h2></div></div>
            <ul className="pricing-feature-list">{t.terms.map((term) => <li className="included" key={term}><CheckCircle2 size={15} aria-hidden="true" /><span>{term}</span></li>)}</ul>
            <p>{t.reviewed}</p>
            <button type="button" className="pricing-plan-button primary" onClick={() => navigate(DASHBOARD_ROUTES.myPlan)}>{t.manage}</button>
          </section>
      </section>
    </main>
  );
}
