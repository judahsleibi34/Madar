import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  CalendarDays,
  CheckCircle2,
  Database,
  FileText,
  Globe2,
  HardDrive,
} from "lucide-react";
import { getPricingContent } from "../../content";
import { PUBLIC_ROUTES, DASHBOARD_ROUTES } from "../../config/routes";
import { BILLING_API_ROUTES } from "../../services/apiRoutes";
import {
  apiFetch,
  getApiUrl,
  readApiErrorCode,
} from "../../utils/apiClient";
import SubscriptionStatusModal from "./SubscriptionStatusModal";

const MODULE_ICONS = {
  cms: Globe2,
  forms: FileText,
  reservations: CalendarDays,
};

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

function getPlanForTools(tools) {
  if (tools.cms && tools.forms && tools.reservations) return "complete";
  if (tools.cms && (tools.forms || tools.reservations)) return "cms-plus";
  if (tools.cms) return "cms";
  if (tools.forms) return "forms-data";
  return "cms";
}

function getToolsForPlan(planId) {
  if (planId === "forms-data") {
    return { cms: false, forms: true, reservations: false };
  }

  if (planId === "cms-plus") {
    return { cms: true, forms: true, reservations: false };
  }

  if (planId === "complete") {
    return { cms: true, forms: true, reservations: true };
  }

  return { cms: true, forms: false, reservations: false };
}

export default function BasePlansPage({ lang = "en" }) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const isArabic = activeLang === "ar";
  const t = getPricingContent(activeLang);
  const navigate = useNavigate();
  const location = useLocation();
  const showBackButton = location.pathname !== PUBLIC_ROUTES.pricing;

  const [selectedTools, setSelectedTools] = useState({
    cms: true,
    forms: true,
    reservations: false,
  });
  const [submittingId, setSubmittingId] = useState(null);
  const [modalState, setModalState] = useState({
    open: false,
    type: "success",
    title: "",
    message: "",
  });

  const selectedPlanId = getPlanForTools(selectedTools);
  const selectedPlan =
    t.basePlans.find((plan) => plan.id === selectedPlanId) || t.basePlans[0];

  const toggleTool = (toolId) => {
    setSelectedTools((current) => {
      const next = {
        ...current,
        [toolId]: !current[toolId],
      };

      if (toolId === "reservations" && next.reservations) {
        next.cms = true;
      }

      if (toolId === "cms" && !next.cms) {
        next.reservations = false;
      }

      if (!next.cms && !next.forms && !next.reservations) {
        next[toolId] = true;
      }

      return next;
    });
  };

  const handleSubscribe = async (plan) => {
    setSubmittingId(plan.id);

    try {
      const response = await apiFetch(getApiUrl(BILLING_API_ROUTES.checkout), {
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
        const errorCode = readApiErrorCode(data);
        setModalState({
          open: true,
          type:
            response.status === 401
              ? "login"
              : errorCode === "billing_not_configured"
                ? "success"
                : "error",
          title:
            errorCode === "billing_not_configured" ? t.requestTitle : "",
          message:
            response.status === 401
              ? t.loginRequired
              : errorCode === "billing_not_configured"
                ? t.availabilityNotice
              : getFriendlySubscriptionError(data?.detail, activeLang),
        });
        return;
      }

      setModalState({
        open: true,
        type: "success",
        title: t.requestTitle,
        message:
          data?.checkout_available === false || data?.requires_payment === false
            ? data?.message || t.requestSaved
            : t.success,
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
      title: "",
      message: "",
    });

    if (type === "success") navigate(DASHBOARD_ROUTES.myPlan);
    if (type === "login") navigate(PUBLIC_ROUTES.login);
  };

  return (
    <main className="pricing-page" dir={isArabic ? "rtl" : "ltr"}>
      <section className="pricing-inner-header">
        {showBackButton && (
          <button
            type="button"
            className="pricing-back-button"
            onClick={() => navigate(PUBLIC_ROUTES.pricing)}
          >
            {"<- "}{isArabic ? "ط±ط¬ظˆط¹" : "Back"}
          </button>
        )}

        <div className="pricing-section-heading">
          <h2>{t.basePlansTitle}</h2>
          <p>{t.basePlansSubtitle}</p>
          <p role="note"><strong>{t.availabilityNotice}</strong></p>
        </div>
      </section>

      <section className="pricing-base-section">
        <div className="pricing-builder">
          <section
            className="pricing-tool-panel"
            aria-labelledby="pricing-tool-title"
          >
            <div className="pricing-panel-heading">
              <h3 id="pricing-tool-title">{t.chooserTitle}</h3>
              <p>{t.chooserSubtitle}</p>
            </div>

            <div className="pricing-tool-list">
              {t.modules.map((module) => {
                const Icon = MODULE_ICONS[module.id] || Database;
                const checked = selectedTools[module.id];

                return (
                  <button
                    key={module.id}
                    type="button"
                    className={`pricing-tool-toggle ${checked ? "is-on" : ""}`}
                    onClick={() => toggleTool(module.id)}
                    aria-pressed={checked}
                  >
                    <span className="pricing-tool-icon" aria-hidden="true">
                      <Icon size={20} />
                    </span>

                    <span className="pricing-tool-copy">
                      <strong>{module.name}</strong>
                      <small>{module.description}</small>
                    </span>

                    <span className="pricing-switch" aria-hidden="true">
                      <span />
                    </span>
                  </button>
                );
              })}
            </div>

            {selectedTools.reservations && (
              <p className="pricing-tool-note">{t.reservationNeedsCms}</p>
            )}
          </section>

          <aside className="pricing-recommendation" aria-label={t.yourPlan}>
            <h3>{selectedPlan.name}</h3>
            <p className="pricing-plan-description">
              {selectedPlan.description}
            </p>

            <div className="pricing-price-row">
              <strong>{selectedPlan.price}</strong>
              <span>{t.perMonth}</span>
            </div>

            <div className="pricing-plan-meta">
              <div>
                <span>{t.bestFor}</span>
                <p>{selectedPlan.bestFor}</p>
              </div>

              <div>
                <span>{t.workflow}</span>
                <p>{selectedPlan.workflow}</p>
              </div>
            </div>

            <div className="pricing-limit-list">
              <span>{t.includedInPlan}</span>
              <ul>
                {selectedPlan.includes.map((item) => (
                  <li key={item}>
                    <CheckCircle2 size={15} aria-hidden="true" />
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            {selectedPlan.id === "complete" && (
              <div className="pricing-storage-callout">
                <HardDrive size={18} aria-hidden="true" />
                <p>
                  Save files on your device when you want local copies, or keep
                  them on the server so your team can access them from the
                  workspace.
                </p>
              </div>
            )}

            <button
              type="button"
              className="pricing-plan-button primary"
              disabled={submittingId === selectedPlan.id}
              onClick={() => handleSubscribe(selectedPlan)}
            >
              {submittingId === selectedPlan.id ? t.saving : selectedPlan.cta}
            </button>
          </aside>
        </div>

        <div className="pricing-compare">
          <span className="pricing-eyebrow">{t.comparePlans}</span>

          <div className="pricing-plan-strip">
            {t.basePlans.map((plan) => (
              <button
                key={plan.id}
                type="button"
                className={`pricing-mini-plan ${
                  plan.id === selectedPlan.id ? "is-selected" : ""
                }`}
                onClick={() => setSelectedTools(getToolsForPlan(plan.id))}
              >
                <span>{plan.name}</span>
                <strong>{plan.price}</strong>
                <small>{plan.description}</small>
              </button>
            ))}
          </div>
        </div>
      </section>

      <SubscriptionStatusModal
        open={modalState.open}
        type={modalState.type}
        lang={activeLang}
        title={modalState.title}
        message={modalState.message}
        onConfirm={handleModalConfirm}
      />
    </main>
  );
}
