import { useMemo, useState } from "react";
import "../../styles/admin/MyPlanPage.css";
import { getMyPlanContent } from "../../content";

export default function MyPlanPage({ lang = "en" }) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const isArabic = activeLang === "ar";
  const t = getMyPlanContent(lang);

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
