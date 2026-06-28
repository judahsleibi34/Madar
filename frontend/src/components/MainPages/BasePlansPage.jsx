import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { getPricingContent } from "../../content";
import { apiFetch } from "../../utils/apiClient";
import SubscriptionStatusModal from "./SubscriptionStatusModal";

const API_URL = import.meta.env.VITE_API_URL || "/api";

function getFriendlySubscriptionError(errorDetail, lang = "en") {
  const text =
    typeof errorDetail === "string"
      ? errorDetail
      : JSON.stringify(errorDetail || "");

  const isArabic = lang === "ar";

  if (text.includes("duplicate key value") || text.includes("already exists")) {
    return isArabic
      ? "هذا الاشتراك موجود بالفعل في حسابك."
      : "This subscription is already active on your account.";
  }

  if (text.includes("User does not have a tenant_id")) {
    return isArabic
      ? "لا يمكن العثور على مساحة العمل الخاصة بحسابك. يرجى تسجيل الدخول مرة أخرى."
      : "We could not find your workspace. Please log in again.";
  }

  return isArabic
    ? "تعذر حفظ الاشتراك. يرجى المحاولة مرة أخرى."
    : "Could not save your subscription. Please try again.";
}

export default function BasePlansPage({ lang = "en" }) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const isArabic = activeLang === "ar";
  const t = getPricingContent(activeLang);
  const navigate = useNavigate();

  const [submittingId, setSubmittingId] = useState(null);
  const [modalState, setModalState] = useState({
    open: false,
    type: "success",
    message: "",
  });

  const handleSubscribe = async (plan) => {
    setSubmittingId(plan.id);

    try {
      const response = await apiFetch(`${API_URL}/billing/checkout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          subscription_type: "full_platform",
          plan: plan.billingPlan || plan.id,
          builder_type: null,
        }),
      });

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        setModalState({
          open: true,
          type: response.status === 401 ? "login" : "error",
          message:
            response.status === 401
              ? t.loginRequired
              : getFriendlySubscriptionError(data?.detail, activeLang),
        });
        return;
      }

      setModalState({
        open: true,
        type: "success",
        message: t.success,
      });
    } catch (error) {
      console.error("Subscription request failed:", error);

      setModalState({
        open: true,
        type: "error",
        message: t.serverError,
      });
    } finally {
      setSubmittingId(null);
    }
  };

  const handleModalConfirm = () => {
    const type = modalState.type;

    setModalState({
      open: false,
      type: "success",
      message: "",
    });

    if (type === "success") navigate("/my-plan");
    if (type === "login") navigate("/login");
  };

  return (
    <main className="pricing-page" dir={isArabic ? "rtl" : "ltr"}>
      <section className="pricing-inner-header">
        <button
          type="button"
          className="pricing-back-button"
          onClick={() => navigate("/pricing")}
        >
          ← {isArabic ? "رجوع" : "Back"}
        </button>

        <div className="pricing-section-heading">
          <span>{t.basePlansLabel}</span>
          <h2>{t.basePlansTitle}</h2>
          <p>{t.basePlansSubtitle}</p>
        </div>
      </section>

      <section className="pricing-base-section">
        <div className="pricing-plan-grid">
          {t.basePlans.map((plan) => (
            <article
              key={plan.id}
              className={`pricing-plan-card ${
                plan.recommended ? "recommended" : ""
              }`}
            >
              <div className="pricing-plan-content">
                <div className="pricing-plan-top">
                  <span>{plan.badge}</span>
                  {plan.recommended && <strong>{t.recommended}</strong>}
                </div>

                <h3>{plan.name}</h3>
                <p className="pricing-plan-description">
                  {plan.description}
                </p>

                <div className="pricing-price-row">
                  <strong>{plan.price}</strong>
                  <span>{t.perMonth}</span>
                </div>

                <div className="pricing-plan-meta">
                  <div>
                    <span>{t.bestFor}</span>
                    <p>{plan.bestFor}</p>
                  </div>

                  <div>
                    <span>{t.workflow}</span>
                    <p>{plan.workflow}</p>
                  </div>
                </div>

                <div className="pricing-limit-list">
                  <span>{t.includes}</span>
                  <ul>
                    {plan.includes.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>

                <ul className="pricing-feature-list">
                  {plan.features.map((feature) => (
                    <li
                      key={feature.text}
                      className={feature.included ? "included" : "muted"}
                    >
                      <span>{feature.included ? "✓" : "—"}</span>
                      {feature.text}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="pricing-plan-footer">
                <button
                  type="button"
                  className={`pricing-plan-button ${
                    plan.recommended ? "primary" : "secondary"
                  }`}
                  disabled={submittingId === plan.id}
                  onClick={() => handleSubscribe(plan)}
                >
                  {submittingId === plan.id ? t.saving : plan.cta}
                </button>
              </div>
            </article>
          ))}
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
