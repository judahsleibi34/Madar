import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import GradientText from "../Animations/GradientText";
import SubscriptionStatusModal from "./SubscriptionStatusModal";

const API_URL = import.meta.env.VITE_API_URL || "/api";

const pageText = {
  en: {
    header: "Flexible pricing for every builder",
    subheader:
      "Choose the full Madar platform, or subscribe only to the builder you need.",
    platformTab: "Full platform plans",
    buildersTab: "Individual builders",
    popular: "Most popular",
    perMonth: "/ month",
    getStarted: "Get started",
    chooseBuilder: "Choose builder",
    galleryHint: "Tap a builder to preview its plan",
    previous: "Previous",
    next: "Next",
    saving: "Saving...",
    success: "Checkout request saved. Payment setup is not connected yet.",
    loginRequired: "Please log in before choosing a plan.",
    failed: "Could not start checkout.",
    serverError: "Could not connect to server.",
    plans: [
      {
        id: "starter",
        name: "Starter",
        price: "$9",
        desc: "Launch a simple website, collect form data, and manage basic reservations.",
        badge: "Website + forms",
        features: [
          { text: "1 website project", included: true },
          { text: "Page builder", included: true },
          { text: "Basic form builder", included: true },
          { text: "Reservation block", included: true },
          { text: "Responses dashboard", included: true },
          { text: "Up to 3 users", included: true },
          { text: "Data workspace", included: false },
          { text: "Advanced reports", included: false },
          { text: "API integrations", included: false },
        ],
      },
      {
        id: "pro",
        name: "Pro",
        price: "$29",
        desc: "Build operational workflows with forms, quizzes, reports, and analysis.",
        badge: "Best value",
        features: [
          { text: "Everything in Starter", included: true },
          { text: "Advanced form builder", included: true },
          { text: "Quiz builder", included: true },
          { text: "Reservation management", included: true },
          { text: "Data workspace", included: true },
          { text: "Spreadsheet upload", included: true },
          { text: "Report builder", included: true },
          { text: "Roles and permissions", included: true },
          { text: "API access", included: true },
        ],
        popular: true,
      },
      {
        id: "business",
        name: "Business",
        price: "$79",
        desc: "For teams that need higher limits, permissions, workflows, and integrations.",
        badge: "For teams",
        features: [
          { text: "Everything in Pro", included: true },
          { text: "Unlimited users", included: true },
          { text: "Advanced workflows", included: true },
          { text: "Advanced analytics", included: true },
          { text: "Custom reports", included: true },
          { text: "Custom domain", included: true },
          { text: "White-label option", included: true },
          { text: "Priority support", included: true },
          { text: "Custom integrations", included: true },
        ],
      },
    ],
    builders: [
      {
        id: "website",
        icon: "◈",
        name: "Website Builder",
        price: "$15",
        desc: "Build responsive pages, sections, elements, templates, and branded sites.",
        badge: "Pages",
        features: [
          { text: "Page builder", included: true },
          { text: "Sections and layouts", included: true },
          { text: "Elements and carousels", included: true },
          { text: "Header and footer editor", included: true },
          { text: "Responsive preview", included: true },
          { text: "Forms and data tools", included: false },
        ],
      },
      {
        id: "forms",
        icon: "▤",
        name: "Form Builder",
        price: "$9",
        desc: "Create forms, collect submissions, and review responses from one workspace.",
        badge: "Forms",
        features: [
          { text: "Unlimited forms", included: true },
          { text: "Field builder", included: true },
          { text: "Required fields", included: true },
          { text: "Responses dashboard", included: true },
          { text: "Export results", included: true },
          { text: "Advanced analysis", included: false },
        ],
      },
      {
        id: "quiz",
        icon: "✓",
        name: "Quiz Builder",
        price: "$9",
        desc: "Create quizzes with scoring, answer keys, timers, and pass/fail results.",
        badge: "Quizzes",
        features: [
          { text: "Question builder", included: true },
          { text: "Correct answer keys", included: true },
          { text: "Automatic scoring", included: true },
          { text: "Manual review mode", included: true },
          { text: "Timers and retakes", included: true },
          { text: "Advanced reports", included: false },
        ],
        popular: true,
      },
      {
        id: "reservation",
        icon: "◷",
        name: "Reservation Builder",
        price: "$9",
        desc: "Accept appointment, service, consultation, or table reservation requests.",
        badge: "Bookings",
        features: [
          { text: "Service selector", included: true },
          { text: "Date and time fields", included: true },
          { text: "Guest count", included: true },
          { text: "Notes and requests", included: true },
          { text: "Reservation submissions", included: true },
          { text: "Advanced workflows", included: false },
        ],
      },
      {
        id: "reports",
        icon: "▣",
        name: "Report Builder",
        price: "$19",
        desc: "Generate finance, operations, and monitoring reports from your data.",
        badge: "Reports",
        features: [
          { text: "Report templates", included: true },
          { text: "Finance reports", included: true },
          { text: "Operations reports", included: true },
          { text: "NGO / MEAL reports", included: true },
          { text: "Data preview", included: true },
          { text: "API integrations", included: false },
        ],
      },
      {
        id: "data",
        icon: "◎",
        name: "Data Workspace",
        price: "$29",
        desc: "Import, clean, inspect, and analyze data from forms, spreadsheets, and APIs.",
        badge: "Analysis",
        features: [
          { text: "Website form data import", included: true },
          { text: "CSV / XLS / XLSX upload", included: true },
          { text: "External link / API import", included: true },
          { text: "Data cleaning", included: true },
          { text: "Backend analysis", included: true },
          { text: "Custom integrations", included: false },
        ],
      },
    ],
  },

  ar: {
    header: "تسعير مرن لكل منشئ",
    subheader:
      "اختر منصة مدار الكاملة، أو اشترك فقط في المنشئ الذي تحتاجه.",
    platformTab: "خطط المنصة الكاملة",
    buildersTab: "المنشئات الفردية",
    popular: "الأكثر شيوعاً",
    perMonth: "/ شهر",
    getStarted: "ابدأ الآن",
    chooseBuilder: "اختر المنشئ",
    galleryHint: "اضغط على منشئ لمعاينة خطته",
    previous: "السابق",
    next: "التالي",
    saving: "جارٍ الحفظ...",
    success: "تم حفظ طلب الدفع. إعداد الدفع غير متصل بعد.",
    loginRequired: "يرجى تسجيل الدخول قبل اختيار خطة.",
    failed: "تعذر بدء الدفع.",
    serverError: "تعذر الاتصال بالخادم.",
    plans: [
      {
        id: "starter",
        name: "المبتدئ",
        price: "$9",
        desc: "أنشئ موقعاً بسيطاً، واجمع بيانات النماذج، وأدر الحجوزات الأساسية.",
        badge: "موقع + نماذج",
        features: [
          { text: "مشروع موقع واحد", included: true },
          { text: "منشئ صفحات", included: true },
          { text: "منشئ نماذج أساسي", included: true },
          { text: "حجوزات أساسية", included: true },
          { text: "لوحة الردود", included: true },
          { text: "حتى 3 مستخدمين", included: true },
          { text: "مساحة البيانات", included: false },
          { text: "تقارير متقدمة", included: false },
          { text: "تكاملات API", included: false },
        ],
      },
      {
        id: "pro",
        name: "الاحترافي",
        price: "$29",
        desc: "أنشئ سير عمل تشغيلي مع النماذج والاختبارات والتقارير والتحليل.",
        badge: "أفضل قيمة",
        features: [
          { text: "كل ميزات المبتدئ", included: true },
          { text: "منشئ نماذج متقدم", included: true },
          { text: "منشئ اختبارات", included: true },
          { text: "إدارة الحجوزات", included: true },
          { text: "مساحة البيانات", included: true },
          { text: "رفع الجداول", included: true },
          { text: "منشئ التقارير", included: true },
          { text: "الأدوار والصلاحيات", included: true },
          { text: "وصول API", included: true },
        ],
        popular: true,
      },
      {
        id: "business",
        name: "الأعمال",
        price: "$79",
        desc: "للفرق التي تحتاج حدوداً أعلى وصلاحيات وسير عمل وتكاملات.",
        badge: "للفرق",
        features: [
          { text: "كل ميزات الاحترافي", included: true },
          { text: "مستخدمون غير محدودين", included: true },
          { text: "سير عمل متقدم", included: true },
          { text: "تحليلات متقدمة", included: true },
          { text: "تقارير مخصصة", included: true },
          { text: "دومين مخصص", included: true },
          { text: "خيار العلامة البيضاء", included: true },
          { text: "دعم ذو أولوية", included: true },
          { text: "تكاملات مخصصة", included: true },
        ],
      },
    ],
    builders: [
      {
        id: "website",
        icon: "◈",
        name: "منشئ المواقع",
        price: "$15",
        desc: "أنشئ صفحات متجاوبة وأقسام وعناصر وقوالب ومواقع بعلامتك التجارية.",
        badge: "صفحات",
        features: [
          { text: "منشئ صفحات", included: true },
          { text: "أقسام وتخطيطات", included: true },
          { text: "عناصر وكاروسيل", included: true },
          { text: "تحرير الهيدر والفوتر", included: true },
          { text: "معاينة متجاوبة", included: true },
          { text: "النماذج وأدوات البيانات", included: false },
        ],
      },
      {
        id: "forms",
        icon: "▤",
        name: "منشئ النماذج",
        price: "$9",
        desc: "أنشئ نماذج، واجمع الردود، وراجع النتائج من مساحة واحدة.",
        badge: "نماذج",
        features: [
          { text: "نماذج غير محدودة", included: true },
          { text: "منشئ الحقول", included: true },
          { text: "حقول مطلوبة", included: true },
          { text: "لوحة الردود", included: true },
          { text: "تصدير النتائج", included: true },
          { text: "تحليل متقدم", included: false },
        ],
      },
      {
        id: "quiz",
        icon: "✓",
        name: "منشئ الاختبارات",
        price: "$9",
        desc: "أنشئ اختبارات مع التصحيح والمفاتيح والمؤقتات ونتائج النجاح والفشل.",
        badge: "اختبارات",
        features: [
          { text: "منشئ أسئلة", included: true },
          { text: "مفاتيح الإجابات", included: true },
          { text: "تصحيح تلقائي", included: true },
          { text: "مراجعة يدوية", included: true },
          { text: "مؤقتات وإعادة محاولات", included: true },
          { text: "تقارير متقدمة", included: false },
        ],
        popular: true,
      },
      {
        id: "reservation",
        icon: "◷",
        name: "منشئ الحجوزات",
        price: "$9",
        desc: "استقبل طلبات المواعيد أو الخدمات أو الاستشارات أو حجوزات الطاولات.",
        badge: "حجوزات",
        features: [
          { text: "اختيار الخدمة", included: true },
          { text: "حقول التاريخ والوقت", included: true },
          { text: "عدد الضيوف", included: true },
          { text: "ملاحظات وطلبات", included: true },
          { text: "ردود الحجوزات", included: true },
          { text: "سير عمل متقدم", included: false },
        ],
      },
      {
        id: "reports",
        icon: "▣",
        name: "منشئ التقارير",
        price: "$19",
        desc: "أنشئ تقارير مالية وتشغيلية وتقارير متابعة من بياناتك.",
        badge: "تقارير",
        features: [
          { text: "قوالب تقارير", included: true },
          { text: "تقارير مالية", included: true },
          { text: "تقارير تشغيلية", included: true },
          { text: "تقارير متابعة وتقييم", included: true },
          { text: "معاينة البيانات", included: true },
          { text: "تكاملات API", included: false },
        ],
      },
      {
        id: "data",
        icon: "◎",
        name: "مساحة البيانات",
        price: "$29",
        desc: "استورد ونظف وراجع وحلل البيانات من النماذج والجداول وواجهات API.",
        badge: "تحليل",
        features: [
          { text: "استيراد بيانات النماذج", included: true },
          { text: "رفع CSV / XLS / XLSX", included: true },
          { text: "استيراد من رابط أو API", included: true },
          { text: "تنظيف البيانات", included: true },
          { text: "تحليل عبر الخادم", included: true },
          { text: "تكاملات مخصصة", included: false },
        ],
      },
    ],
  },
};

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
              {feature.included ? "✓" : "✕"}
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
  const t = pageText[lang] || pageText.en;
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
      const response = await fetch(`${API_URL}/billing/checkout`, {
        method: "POST",
        credentials: "include",
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