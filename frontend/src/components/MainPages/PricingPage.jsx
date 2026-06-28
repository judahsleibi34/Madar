import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import GradientText from "../Animations/GradientText";
import SubscriptionStatusModal from "./SubscriptionStatusModal";
import { apiFetch } from "../../utils/apiClient";
import { getPricingContent } from "../../content";

const API_URL = import.meta.env.VITE_API_URL || "/api";

function getFriendlySubscriptionError(errorDetail, lang = "en") {
  const text =
    typeof errorDetail === "string"
      ? errorDetail
      : JSON.stringify(errorDetail || "");

  const isArabic = lang === "ar";

  if (
    text.includes("duplicate key value") ||
    text.includes("already exists") ||
    text.includes("features_unique_tenant_subscription_idx")
  ) {
    return isArabic
      ? "هذا الاشتراك موجود بالفعل في حسابك."
      : "This subscription is already active on your account.";
  }

  if (text.includes("User does not have a tenant_id")) {
    return isArabic
      ? "لا يمكن العثور على مساحة العمل الخاصة بحسابك. يرجى تسجيل الدخول مرة أخرى."
      : "We could not find your workspace. Please log in again.";
  }

  if (text.includes("builder_type is required")) {
    return isArabic
      ? "يرجى اختيار نوع المنشئ قبل المتابعة."
      : "Please choose a builder before continuing.";
  }

  if (text.includes("builder_type must be null")) {
    return isArabic
      ? "خطة المنصة الكاملة لا تحتاج إلى اختيار منشئ."
      : "Full platform plans do not need a builder selection.";
  }

  if (text.includes("Invalid full platform plan")) {
    return isArabic
      ? "خطة المنصة المختارة غير صالحة."
      : "The selected platform plan is not valid.";
  }

  if (text.includes("Invalid individual builder plan")) {
    return isArabic
      ? "خطة المنشئ المختارة غير صالحة."
      : "The selected builder plan is not valid.";
  }

  return isArabic
    ? "تعذر حفظ الاشتراك. يرجى المحاولة مرة أخرى."
    : "Could not save your subscription. Please try again.";
}

function getCircularOffset(index, activeIndex, total) {
  let offset = index - activeIndex;

  if (offset > total / 2) offset -= total;
  if (offset < -total / 2) offset += total;

  return offset;
}

function getOffsetClass(offset) {
  if (offset <= -2) return "offset-neg-2";
  if (offset === -1) return "offset-neg-1";
  if (offset === 0) return "offset-0";
  if (offset === 1) return "offset-pos-1";
  if (offset >= 2) return "offset-pos-2";
  return "offset-0";
}

function AnimatedBuilderGallery({ items, activeId, onSelect, hint }) {
  const activeItem = items.find((item) => item.id === activeId) || items[0];

  return (
    <section className="builder-gallery-shell" aria-label="Builder selector">
      <div className="builder-gallery-orbit">
        <div className="builder-gallery-core">
          <span>{activeItem.icon}</span>
          <strong>{activeItem.name}</strong>
          <small>{activeItem.price} / month</small>
        </div>

        {items.map((item, index) => {
          const angle = (360 / items.length) * index - 90;
          const isActive = item.id === activeId;

          return (
            <button
              type="button"
              key={item.id}
              className={`builder-orbit-item ${isActive ? "active" : ""}`}
              style={{
                "--angle": `${angle}deg`,
                "--delay": `${index * 0.08}s`,
              }}
              onClick={() => onSelect(item.id)}
              aria-label={item.name}
            >
              <span>{item.icon}</span>
              <strong>{item.badge}</strong>
            </button>
          );
        })}
      </div>

      <div className="builder-gallery-info">
        <span>{hint}</span>
        <h3>{activeItem.name}</h3>
        <p>{activeItem.desc}</p>
      </div>
    </section>
  );
}

function PricingCard({
  plan,
  popularText,
  periodText,
  buttonText,
  onClick,
  isActive,
  offset,
  isSubmitting,
  savingText,
}) {
  const hidden = Math.abs(offset) > 2;
  const offsetClass = getOffsetClass(offset);

  return (
    <article
      className={`pricing-card ${offsetClass} ${plan.popular ? "popular" : ""} ${
        isActive ? "is-active-plan" : ""
      } ${hidden ? "is-hidden-plan" : ""}`}
      aria-hidden={hidden}
    >
      {plan.popular && <div className="popular-badge">{popularText}</div>}

      <div className="plan-top">
        <div className="plan-title-row">
          <p className="plan-name">
            <GradientText pauseOnHover>{plan.name}</GradientText>
          </p>

          {plan.badge && <span className="plan-mini-badge">{plan.badge}</span>}
        </div>

        <div className="plan-price">
          <span className="amount">{plan.price}</span>
          <span className="period">{periodText}</span>
        </div>

        <p className="plan-desc">{plan.desc}</p>
      </div>

      <hr className="plan-divider" />

      <ul className="features-list">
        {plan.features.map((feature, index) => (
          <li
            key={`${plan.name}-${index}`}
            className={feature.included ? "" : "disabled"}
          >
            <span className="feature-icon">
              {feature.included ? "✓" : "×"}
            </span>
            <span>{feature.text}</span>
          </li>
        ))}
      </ul>

      <button
        type="button"
        className={`plan-btn ${plan.popular ? "primary" : ""}`}
        onClick={onClick}
        disabled={isSubmitting}
        tabIndex={hidden ? -1 : 0}
      >
        {isSubmitting ? savingText : buttonText}
      </button>
    </article>
  );
}

export default function PricingPage({ lang = "en" }) {
  const t = getPricingContent(lang);
  const navigate = useNavigate();

  const [activeMode, setActiveMode] = useState("platform");
  const [activePlatformId, setActivePlatformId] = useState("pro");
  const [activeBuilderId, setActiveBuilderId] = useState("quiz");
  const [isPaused, setIsPaused] = useState(false);
  const [submittingPlanId, setSubmittingPlanId] = useState(null);

  const [modalState, setModalState] = useState({
    open: false,
    type: "success",
    message: "",
  });

  const isPlatform = activeMode === "platform";

  const activeItems = useMemo(
    () => (isPlatform ? t.plans : t.builders),
    [isPlatform, t]
  );

  const activePlanId = isPlatform ? activePlatformId : activeBuilderId;

  const activeIndex = Math.max(
    0,
    activeItems.findIndex((item) => item.id === activePlanId)
  );

  const moveCarousel = (direction = "next") => {
    const nextIndex =
      direction === "next"
        ? (activeIndex + 1) % activeItems.length
        : (activeIndex - 1 + activeItems.length) % activeItems.length;

    const nextItem = activeItems[nextIndex];

    if (isPlatform) {
      setActivePlatformId(nextItem.id);
    } else {
      setActiveBuilderId(nextItem.id);
    }
  };

  const handleSubscribe = async (plan) => {
    const payload = isPlatform
      ? {
          subscription_type: "full_platform",
          plan: plan.id,
          builder_type: null,
        }
      : {
          subscription_type: "individual_builder",
          plan: "basic",
          builder_type: plan.id,
        };

    setSubmittingPlanId(plan.id);

    try {
      const response = await apiFetch(`${API_URL}/billing/checkout`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json().catch(() => null);

      if (!response.ok) {
        setModalState({
          open: true,
          type: response.status === 401 ? "login" : "error",
          message:
            response.status === 401
              ? t.loginRequired
              : getFriendlySubscriptionError(data?.detail, lang),
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
      setSubmittingPlanId(null);
    }
  };

  const handleModalConfirm = () => {
    const wasSuccess = modalState.type === "success";

    setModalState({
      open: false,
      type: "success",
      message: "",
    });

    if (wasSuccess) {
      navigate("/my-plan");
    } else if (modalState.type === "login") {
      navigate("/login");
    }
  };

  useEffect(() => {
    if (isPaused) return undefined;

    const timer = window.setInterval(() => {
      moveCarousel("next");
    }, 3000);

    return () => window.clearInterval(timer);
  }, [isPaused, activeIndex, activeMode, lang]);

  return (
    <main className="pricing-page">
      <div className="pricing-header">
        <h1>
          {lang === "en" ? (
            <>
              <GradientText pauseOnHover>Flexible pricing</GradientText> for
              every builder
            </>
          ) : (
            <GradientText pauseOnHover>{t.header}</GradientText>
          )}
        </h1>

        <p>{t.subheader}</p>

        <div className="pricing-tabs" role="tablist" aria-label="Pricing type">
          <button
            type="button"
            className={activeMode === "platform" ? "active" : ""}
            onClick={() => setActiveMode("platform")}
          >
            {t.platformTab}
          </button>

          <button
            type="button"
            className={activeMode === "builders" ? "active" : ""}
            onClick={() => setActiveMode("builders")}
          >
            {t.buildersTab}
          </button>
        </div>
      </div>

      {!isPlatform && (
        <AnimatedBuilderGallery
          items={t.builders}
          activeId={activeBuilderId}
          onSelect={setActiveBuilderId}
          hint={t.galleryHint}
        />
      )}

      <section
        className="pricing-carousel-section"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        <button
          type="button"
          className="pricing-carousel-arrow pricing-carousel-arrow-left"
          onClick={() => moveCarousel("prev")}
          aria-label={t.previous}
        >
          ‹
        </button>

        <div className="pricing-carousel-stage">
          {activeItems.map((plan, index) => {
            const offset = getCircularOffset(
              index,
              activeIndex,
              activeItems.length
            );

            return (
              <PricingCard
                key={plan.id}
                plan={plan}
                offset={offset}
                popularText={t.popular}
                periodText={t.perMonth}
                buttonText={isPlatform ? t.getStarted : t.chooseBuilder}
                savingText={t.saving}
                onClick={() => handleSubscribe(plan)}
                isActive={plan.id === activePlanId}
                isSubmitting={submittingPlanId === plan.id}
              />
            );
          })}
        </div>

        <button
          type="button"
          className="pricing-carousel-arrow pricing-carousel-arrow-right"
          onClick={() => moveCarousel("next")}
          aria-label={t.next}
        >
          ›
        </button>
      </section>

      <SubscriptionStatusModal
        open={modalState.open}
        type={modalState.type}
        lang={lang}
        message={modalState.message}
        onConfirm={handleModalConfirm}
      />
    </main>
  );
}

