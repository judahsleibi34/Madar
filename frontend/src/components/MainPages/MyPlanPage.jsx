import { useMemo, useState } from "react";
import "../../styles/admin/MyPlanPage.css";

const planText = {
  en: {
    kicker: "Plan",
    title: "My Plan",
    subtitle:
      "Manage your Madar subscription, enabled builders, usage, and upgrade options.",
    currentPlan: "Current plan",
    billing: "Billing",
    monthly: "Monthly",
    status: "Active",
    renews: "Renews",
    upgrade: "Upgrade plan",
    manageBilling: "Manage billing",
    includedBuilders: "Included builders",
    availableBuilders: "Available add-ons",
    usageTitle: "Usage overview",
    limitsTitle: "Plan limits",
    active: "Active",
    locked: "Locked",
    included: "Included",
    add: "Add builder",
    perMonth: "/ month",
    planName: "Pro",
    planPrice: "$29",
    planDescription:
      "Build operational workflows with forms, quizzes, reports, reservations, and data analysis.",
    renewalDate: "June 28, 2026",
    usage: [
      { label: "Projects", value: 1, max: 5 },
      { label: "Users", value: 3, max: 10 },
      { label: "Responses", value: 128, max: 1000 },
      { label: "Storage", value: 2.4, max: 10, suffix: "GB" },
    ],
    builders: [
      {
        id: "website",
        icon: "◈",
        name: "Website Builder",
        price: "$15",
        desc: "Responsive pages, sections, templates, branded sites, and publishing.",
        enabled: true,
      },
      {
        id: "forms",
        icon: "▤",
        name: "Form Builder",
        price: "$9",
        desc: "Forms, fields, submissions, exports, and response dashboards.",
        enabled: true,
      },
      {
        id: "quiz",
        icon: "✓",
        name: "Quiz Builder",
        price: "$9",
        desc: "Scoring, answer keys, timers, pass/fail results, and review modes.",
        enabled: true,
      },
      {
        id: "reservation",
        icon: "◷",
        name: "Reservation Builder",
        price: "$9",
        desc: "Appointments, services, date/time fields, guests, and requests.",
        enabled: true,
      },
      {
        id: "reports",
        icon: "▣",
        name: "Report Builder",
        price: "$19",
        desc: "Finance, operations, monitoring, and custom report templates.",
        enabled: true,
      },
      {
        id: "data",
        icon: "◎",
        name: "Data Workspace",
        price: "$29",
        desc: "CSV/XLS uploads, API imports, cleaning, inspection, and analysis.",
        enabled: true,
      },
    ],
  },

  ar: {
    kicker: "الخطة",
    title: "خطتي",
    subtitle:
      "أدر اشتراكك في مدار والمنشئات المفعلة والاستخدام وخيارات الترقية.",
    currentPlan: "الخطة الحالية",
    billing: "الفوترة",
    monthly: "شهرياً",
    status: "نشطة",
    renews: "تتجدد في",
    upgrade: "ترقية الخطة",
    manageBilling: "إدارة الفوترة",
    includedBuilders: "المنشئات المضمنة",
    availableBuilders: "إضافات متاحة",
    usageTitle: "نظرة على الاستخدام",
    limitsTitle: "حدود الخطة",
    active: "مفعل",
    locked: "غير مفعل",
    included: "مضمن",
    add: "إضافة المنشئ",
    perMonth: "/ شهر",
    planName: "الاحترافي",
    planPrice: "$29",
    planDescription:
      "أنشئ سير عمل تشغيلي مع النماذج والاختبارات والتقارير والحجوزات وتحليل البيانات.",
    renewalDate: "28 يونيو 2026",
    usage: [
      { label: "المشاريع", value: 1, max: 5 },
      { label: "المستخدمون", value: 3, max: 10 },
      { label: "الردود", value: 128, max: 1000 },
      { label: "التخزين", value: 2.4, max: 10, suffix: "GB" },
    ],
    builders: [
      {
        id: "website",
        icon: "◈",
        name: "منشئ المواقع",
        price: "$15",
        desc: "صفحات متجاوبة وأقسام وقوالب ومواقع بعلامتك التجارية ونشر.",
        enabled: true,
      },
      {
        id: "forms",
        icon: "▤",
        name: "منشئ النماذج",
        price: "$9",
        desc: "نماذج وحقول وردود وتصدير ولوحات متابعة للنتائج.",
        enabled: true,
      },
      {
        id: "quiz",
        icon: "✓",
        name: "منشئ الاختبارات",
        price: "$9",
        desc: "تصحيح ومفاتيح إجابات ومؤقتات ونتائج نجاح وفشل ومراجعة.",
        enabled: true,
      },
      {
        id: "reservation",
        icon: "◷",
        name: "منشئ الحجوزات",
        price: "$9",
        desc: "مواعيد وخدمات وحقول تاريخ ووقت وعدد ضيوف وطلبات.",
        enabled: true,
      },
      {
        id: "reports",
        icon: "▣",
        name: "منشئ التقارير",
        price: "$19",
        desc: "تقارير مالية وتشغيلية ومتابعة وقوالب تقارير مخصصة.",
        enabled: true,
      },
      {
        id: "data",
        icon: "◎",
        name: "مساحة البيانات",
        price: "$29",
        desc: "رفع CSV/XLS واستيراد API وتنظيف البيانات ومراجعتها وتحليلها.",
        enabled: true,
      },
    ],
  },
};

export default function MyPlanPage({ lang = "en" }) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const isArabic = activeLang === "ar";
  const t = planText[activeLang];

  const [selectedBuilderId, setSelectedBuilderId] = useState("data");

  const selectedBuilder = useMemo(
    () => t.builders.find((builder) => builder.id === selectedBuilderId) || t.builders[0],
    [selectedBuilderId, t.builders]
  );

  return (
    <section className="my-plan-page" dir={isArabic ? "rtl" : "ltr"}>
      <header className="my-plan-hero">
        <div>
          <h1>{t.title}</h1>
          <p>{t.subtitle}</p>
        </div>

        <div className="my-plan-hero-actions">
          <button type="button" className="my-plan-secondary-btn">
            {t.manageBilling}
          </button>
          <button type="button" className="my-plan-primary-btn">
            {t.upgrade}
          </button>
        </div>
      </header>

      <div className="my-plan-grid">
        <article className="my-plan-current-card">
          <div className="my-plan-card-top">
            <span>{t.currentPlan}</span>
            <strong>{t.status}</strong>
          </div>

          <div className="my-plan-price-row">
            <h2>{t.planName}</h2>
            <div>
              <strong>{t.planPrice}</strong>
              <span>{t.perMonth}</span>
            </div>
          </div>

          <p>{t.planDescription}</p>

          <div className="my-plan-meta-grid">
            <div>
              <span>{t.billing}</span>
              <strong>{t.monthly}</strong>
            </div>
            <div>
              <span>{t.renews}</span>
              <strong>{t.renewalDate}</strong>
            </div>
          </div>
        </article>

        <article className="my-plan-feature-card">
          <div className="my-plan-builder-icon">{selectedBuilder.icon}</div>
          <span>{t.included}</span>
          <h2>{selectedBuilder.name}</h2>
          <p>{selectedBuilder.desc}</p>
          <strong>
            {selectedBuilder.price} {t.perMonth}
          </strong>
        </article>
      </div>

      <section className="my-plan-section">
        <div className="my-plan-section-header">
          <div>
            <span className="my-plan-kicker">{t.usageTitle}</span>
            <h2>{t.limitsTitle}</h2>
          </div>
        </div>

        <div className="my-plan-usage-grid">
          {t.usage.map((item) => {
            const percent = Math.min(100, Math.round((item.value / item.max) * 100));

            return (
              <article key={item.label} className="my-plan-usage-card">
                <div>
                  <span>{item.label}</span>
                  <strong>
                    {item.value}
                    {item.suffix ? item.suffix : ""} / {item.max}
                    {item.suffix ? item.suffix : ""}
                  </strong>
                </div>

                <div className="my-plan-progress-track">
                  <span style={{ width: `${percent}%` }} />
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="my-plan-section">
        <div className="my-plan-section-header">
          <div>
            <span className="my-plan-kicker">{t.includedBuilders}</span>
            <h2>{t.availableBuilders}</h2>
          </div>
        </div>

        <div className="my-plan-builders-grid">
          {t.builders.map((builder) => (
            <button
              key={builder.id}
              type="button"
              className={`my-plan-builder-card ${
                selectedBuilderId === builder.id ? "active" : ""
              }`}
              onClick={() => setSelectedBuilderId(builder.id)}
            >
              <div className="my-plan-builder-card-top">
                <span className="my-plan-builder-mini-icon">{builder.icon}</span>
                <strong>{builder.enabled ? t.active : t.locked}</strong>
              </div>

              <h3>{builder.name}</h3>
              <p>{builder.desc}</p>

              <div className="my-plan-builder-footer">
                <span>
                  {builder.price} {t.perMonth}
                </span>
                <em>{builder.enabled ? t.included : t.add}</em>
              </div>
            </button>
          ))}
        </div>
      </section>
    </section>
  );
}