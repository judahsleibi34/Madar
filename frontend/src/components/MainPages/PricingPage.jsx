import { useNavigate } from "react-router-dom";
import { getPricingContent } from "../../content";
import { PUBLIC_ROUTES } from "../../config/routes";

export default function PricingPage({ lang = "en" }) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const isArabic = activeLang === "ar";
  const t = getPricingContent(activeLang);
  const navigate = useNavigate();

  return (
    <main className="pricing-page pricing-choice-page" dir={isArabic ? "rtl" : "ltr"}>
      <section className="pricing-hero pricing-choice-hero">
        <div className="pricing-hero-copy">
          <span className="pricing-eyebrow">{t.eyebrow}</span>
          <h1>{t.header}</h1>
          <p>{t.subheader}</p>
        </div>

        <div className="pricing-choice-grid" aria-label="Pricing options">
          <button
            type="button"
            className="pricing-choice-card active"
            onClick={() => navigate(PUBLIC_ROUTES.pricingBasePlans)}
          >
            <span>{t.basePlansTab}</span>
            <strong>{t.basePlansTitle}</strong>
            <p>{t.basePlansSubtitle}</p>
            <em aria-hidden="true">→</em>
          </button>

          <button
            type="button"
            className="pricing-choice-card"
            onClick={() => navigate(PUBLIC_ROUTES.pricingCustomPlan)}
          >
            <span>{t.customPlansTab}</span>
            <strong>{t.customPlans.title}</strong>
            <p>{t.customPlans.subtitle}</p>
            <em aria-hidden="true">→</em>
          </button>
        </div>
      </section>
    </main>
  );
}
