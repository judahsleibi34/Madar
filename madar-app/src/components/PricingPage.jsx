import { useState } from "react";
import { useNavigate } from "react-router-dom";

const pageText = {
  en: {
    header: "Flexible plans for every need",
    subheader: "Choose the plan that fits your business. Upgrade anytime.",
    popular: "Most popular",
    perMonth: "/ month",
    getStarted: "Get started",
    plans: [
      {
        name: "Starter",
        price: 9,
        desc: "Perfect for small teams just getting started.",
        features: [
          { text: "Up to 3 users", included: true },
          { text: "Basic dashboard", included: true },
          { text: "Task management", included: true },
          { text: "Email support", included: true },
          { text: "Advanced analytics", included: false },
          { text: "API access", included: false },
          { text: "Custom integrations", included: false },
        ],
        popular: false,
      },
      {
        name: "Pro",
        price: 29,
        desc: "For growing businesses that need more power.",
        features: [
          { text: "Up to 15 users", included: true },
          { text: "Advanced dashboard", included: true },
          { text: "Task management", included: true },
          { text: "Priority support", included: true },
          { text: "Advanced analytics", included: true },
          { text: "API access", included: true },
          { text: "Custom integrations", included: false },
        ],
        popular: true,
      },
      {
        name: "Enterprise",
        price: 79,
        desc: "Full power for large teams and organizations.",
        features: [
          { text: "Unlimited users", included: true },
          { text: "Advanced dashboard", included: true },
          { text: "Task management", included: true },
          { text: "24/7 dedicated support", included: true },
          { text: "Advanced analytics", included: true },
          { text: "API access", included: true },
          { text: "Custom integrations", included: true },
        ],
        popular: false,
      },
    ],
  },
  ar: {
    header: "خطط مرنة لكل احتياج",
    subheader: "اختر الخطة المناسبة لعملك. يمكنك الترقية في أي وقت.",
    popular: "الأكثر شيوعاً",
    perMonth: "/ شهر",
    getStarted: "ابدأ الآن",
    plans: [
      {
        name: "المبتدئ",
        price: 9,
        desc: "مثالي للفرق الصغيرة التي تبدأ للتو.",
        features: [
          { text: "حتى 3 مستخدمين", included: true },
          { text: "لوحة تحكم أساسية", included: true },
          { text: "إدارة المهام", included: true },
          { text: "دعم عبر البريد الإلكتروني", included: true },
          { text: "تحليلات متقدمة", included: false },
          { text: "وصول إلى API", included: false },
          { text: "تكاملات مخصصة", included: false },
        ],
        popular: false,
      },
      {
        name: "الاحترافي",
        price: 29,
        desc: "للشركات المتنامية التي تحتاج إلى مزيد من القوة.",
        features: [
          { text: "حتى 15 مستخدماً", included: true },
          { text: "لوحة تحكم متقدمة", included: true },
          { text: "إدارة المهام", included: true },
          { text: "دعم ذو أولوية", included: true },
          { text: "تحليلات متقدمة", included: true },
          { text: "وصول إلى API", included: true },
          { text: "تكاملات مخصصة", included: false },
        ],
        popular: true,
      },
      {
        name: "المؤسسات",
        price: 79,
        desc: "القوة الكاملة للفرق والمؤسسات الكبيرة.",
        features: [
          { text: "مستخدمون غير محدودين", included: true },
          { text: "لوحة تحكم متقدمة", included: true },
          { text: "إدارة المهام", included: true },
          { text: "دعم مخصص على مدار الساعة", included: true },
          { text: "تحليلات متقدمة", included: true },
          { text: "وصول إلى API", included: true },
          { text: "تكاملات مخصصة", included: true },
        ],
        popular: false,
      },
    ],
  },
};

export default function PricingPage({ lang = "en" }) {
  const t = pageText[lang] || pageText.en;
  const navigate = useNavigate();

  return (
    <main className="pricing-page">
      <div className="pricing-header">
        <h1>{t.header}</h1>
        <p>{t.subheader}</p>
      </div>

      <div className="pricing-grid">
        {t.plans.map((plan) => (
          <div
            key={plan.name}
            className={`pricing-card ${plan.popular ? "popular" : ""}`}
          >
            {plan.popular && (
              <div className="popular-badge">{t.popular}</div>
            )}

            <div className="plan-top">
              <p className="plan-name">{plan.name}</p>
              <div className="plan-price">
                <span className="amount">${plan.price}</span>
                <span className="period">{t.perMonth}</span>
              </div>
              <p className="plan-desc">{plan.desc}</p>
            </div>

            <hr className="plan-divider" />

            <ul className="features-list">
              {plan.features.map((feature, i) => (
                <li key={i} className={feature.included ? "" : "disabled"}>
                  <span className="feature-icon">
                    {feature.included ? "✓" : "✕"}
                  </span>
                  {feature.text}
                </li>
              ))}
            </ul>

            <button
              className={`plan-btn ${plan.popular ? "primary" : ""}`}
              onClick={() => navigate("/signup")}
            >
              {t.getStarted}
            </button>
          </div>
        ))}
      </div>
    </main>
  );
}