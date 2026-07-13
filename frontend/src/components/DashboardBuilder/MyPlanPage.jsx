import { useEffect, useState } from "react";
import { CreditCard, ExternalLink } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useLanguage } from "../../i18n";
import { BILLING_API_ROUTES } from "../../services/apiRoutes";
import { apiFetch, getApiUrl, readApiError } from "../../utils/apiClient";

const titleCase = (value) =>
  String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

export const getBillingDisplayState = (billing) => {
  const active = billing?.active || null;
  const rawPending = billing?.pending_request || null;
  const samePlan = (left, right) => Boolean(left && right) &&
    String(left.subscription_type || "") === String(right.subscription_type || "") &&
    String(left.builder_type || "") === String(right.builder_type || "") &&
    String(left.plan || "") === String(right.plan || "");
  const pending = samePlan(active, rawPending) ? null : rawPending;
  const current = active || billing?.current || pending || null;
  const cards = [
    ...(active ? [{ kind: "active", feature: active }] : []),
    ...(pending ? [{ kind: "pending", feature: pending }] : []),
  ];
  if (!cards.length && current) {
    cards.push({
      kind: current.payment_status === "pending" ? "pending" : "other",
      feature: current,
    });
  }
  return { active, pending, current, state: current?.payment_status || "none", cards };
};

export default function MyPlanPage() {
  const { direction, language } = useLanguage();
  const navigate = useNavigate();
  const isArabic = language === "ar";
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    const loadBilling = async () => {
      try {
        const response = await apiFetch(getApiUrl(BILLING_API_ROUTES.current), {
          method: "GET",
          cache: "no-store",
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(readApiError(data, "Could not load billing state."));
        if (!cancelled) setBilling(data.billing || {});
      } catch (loadError) {
        if (!cancelled) setError(loadError.message || "Could not load billing state.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadBilling();
    return () => { cancelled = true; };
  }, []);

  const view = getBillingDisplayState(billing);
  const copy = isArabic
    ? {
        title: "خطتي",
        subtitle: "حالة الخطة المحفوظة لمساحة العمل الحالية.",
        loading: "جارٍ تحميل حالة الخطة...",
        empty: "لم يتم طلب أو تفعيل خطة بعد.",
        choose: "اختيار خطة",
        active: "الخطة النشطة",
        pending: "طلب قيد المراجعة اليدوية",
        noPayment: "لم يتم تحصيل أي دفعة. الدفع الإلكتروني غير متاح حالياً.",
        review: "مراجعة الخطط",
      }
    : {
        title: "My Plan",
        subtitle: "Persisted plan status for this workspace.",
        loading: "Loading your plan status...",
        empty: "No plan has been requested or activated yet.",
        choose: "Choose a plan",
        active: "Active plan",
        pending: "Pending manual review",
        noPayment: "No payment has been taken. Online payment is not available yet.",
        review: "Review plans",
      };

  const renderFeature = (feature, label) => feature && (
    <article className="my-plan-current-card">
      <div className="my-plan-card-top">
        <div>
          <span>{label}</span>
          <h2>{titleCase(feature.plan || feature.subscription_type)}</h2>
        </div>
        <strong>{titleCase(feature.payment_status)}</strong>
      </div>
      <p>{titleCase(feature.subscription_type)}</p>
      {feature.builder_type && <p>{titleCase(feature.builder_type)}</p>}
      {feature.payment_status === "pending" && <p role="note">{copy.noPayment}</p>}
    </article>
  );

  return (
    <section className="my-plan-page" dir={direction}>
      <header className="my-plan-header">
        <div>
          <span className="my-plan-eyebrow">{copy.title}</span>
          <h1>{copy.title}</h1>
          <p>{copy.subtitle}</p>
        </div>
        <button className="my-plan-button primary" type="button" onClick={() => navigate("/pricing")}>
          <CreditCard size={17} /> {copy.review}
        </button>
      </header>

      {loading && <div className="my-plan-current-card" role="status">{copy.loading}</div>}
      {!loading && error && <div className="my-plan-current-card" role="alert">{error}</div>}
      {!loading && !error && !view.current && (
        <div className="my-plan-current-card">
          <p>{copy.empty}</p>
          <button className="my-plan-button primary" type="button" onClick={() => navigate("/pricing")}>
            <ExternalLink size={17} /> {copy.choose}
          </button>
        </div>
      )}
      {!loading && !error && view.cards.map(({ kind, feature }) => (
        <div key={`${kind}:${feature.id || `${feature.subscription_type}:${feature.builder_type || "all"}:${feature.plan}`}`}>
          {renderFeature(
            feature,
            kind === "active" ? copy.active : kind === "pending" ? copy.pending : titleCase(feature.payment_status)
          )}
        </div>
      ))}
    </section>
  );
}
