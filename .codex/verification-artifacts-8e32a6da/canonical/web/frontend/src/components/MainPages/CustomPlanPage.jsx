import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getPricingContent } from "../../content";
import { DASHBOARD_ROUTES, PUBLIC_ROUTES } from "../../config/routes";
import SubscriptionStatusModal from "./SubscriptionStatusModal";

export default function CustomPlanPage({ lang = "en" }) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const isArabic = activeLang === "ar";
  const t = getPricingContent(activeLang);
  const navigate = useNavigate();

  const [modalState, setModalState] = useState({
    open: false,
    type: "success",
    message: "",
  });

  const [selectedModules, setSelectedModules] = useState(() =>
    t.customPlans.modules
      .filter((module) => module.defaultSelected)
      .map((module) => module.id)
  );

  const selectedModuleItems = useMemo(() => {
    return t.customPlans.modules.filter((module) =>
      selectedModules.includes(module.id)
    );
  }, [selectedModules, t.customPlans.modules]);

  const customPrice = useMemo(() => {
    return selectedModuleItems.reduce(
      (sum, module) => sum + module.priceValue,
      0
    );
  }, [selectedModuleItems]);

  const toggleModule = (moduleId) => {
    setSelectedModules((current) =>
      current.includes(moduleId)
        ? current.filter((id) => id !== moduleId)
        : [...current, moduleId]
    );
  };

  const handleCustomPlanRequest = () => {
    setModalState({
      open: true,
      type: "success",
      message: t.customPlans.requestSaved || t.success,
    });
  };

  const handleModalConfirm = () => {
    const type = modalState.type;

    setModalState({
      open: false,
      type: "success",
      message: "",
    });

    if (type === "success") navigate(DASHBOARD_ROUTES.myPlan);
    if (type === "login") navigate(PUBLIC_ROUTES.login);
  };

  return (
    <main className="pricing-page" dir={isArabic ? "rtl" : "ltr"}>
      <section className="pricing-inner-header app-page-intro">
        <button
          type="button"
          className="pricing-back-button"
          onClick={() => navigate(PUBLIC_ROUTES.pricing)}
        >
          {"<- "}{isArabic ? "ط±ط¬ظˆط¹" : "Back"}
        </button>

        <div className="pricing-section-heading">
          <span>{t.customPlans.label}</span>
          <h1>{t.customPlans.title}</h1>
          <p>{t.customPlans.subtitle}</p>
        </div>
      </section>

      <section className="pricing-custom-section">
        <div className="pricing-custom-layout">
          <div className="pricing-module-list">
            {t.customPlans.modules.map((module) => {
              const isSelected = selectedModules.includes(module.id);

              return (
                <button
                  key={module.id}
                  type="button"
                  className={`pricing-module-card ${
                    isSelected ? "selected" : ""
                  }`}
                  onClick={() => toggleModule(module.id)}
                >
                  <div className="pricing-module-check">
                    <span>{isSelected ? "✓" : "+"}</span>
                  </div>

                  <div className="pricing-module-content">
                    <div className="pricing-module-head">
                      <strong>{module.name}</strong>
                      <em>
                        {module.price}
                        {t.perMonth}
                      </em>
                    </div>

                    <p>{module.description}</p>
                    <small>{module.value}</small>
                  </div>
                </button>
              );
            })}
          </div>

          <aside className="pricing-custom-summary">

            <h3>{t.customPlans.summaryTitle}</h3>
            <p>{t.customPlans.summaryText}</p>

            <div className="pricing-custom-price">
              <span>{t.customPlans.estimatedPrice}</span>
              <strong>
                ${customPrice}
                <small>{t.perMonth}</small>
              </strong>
            </div>

            <div className="pricing-selected-modules">
              <span>{t.customPlans.selectedModules}</span>

              {selectedModuleItems.length > 0 ? (
                <ul>
                  {selectedModuleItems.map((module) => (
                    <li key={module.id}>
                      <strong>{module.name}</strong>
                      <em>
                        {module.price}
                        {t.perMonth}
                      </em>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>{t.customPlans.noModules}</p>
              )}
            </div>

            <button
              type="button"
              className="pricing-plan-button primary"
              onClick={handleCustomPlanRequest}
            >
              {t.customPlans.requestPlan}
            </button>

            <small className="pricing-summary-note">
              {t.customPlans.note}
            </small>
          </aside>
        </div>
      </section>

      <SubscriptionStatusModal
        open={modalState.open}
        type={modalState.type}
        lang={activeLang}
        message={modalState.message}
        onConfirm={handleModalConfirm}
      />
    </main>
  );
}
