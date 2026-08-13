import { useEffect, useMemo, useState } from "react";
import { CreditCard, ExternalLink } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useLanguage } from "../../i18n";
import { BILLING_API_ROUTES } from "../../services/apiRoutes";
import { apiFetch, getApiUrl, readApiError } from "../../utils/apiClient";

const fetchJson = async (path) => {
  const response = await apiFetch(getApiUrl(path), { method: "GET", cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(readApiError(data, "Could not load plan data."));
  return data;
};

const formatBytes = (bytes) => `${(Number(bytes || 0) / 1024 ** 3).toFixed(1)} GB`;
const formatNumber = (value) => new Intl.NumberFormat("en-US").format(Number(value || 0));
const formatPrice = (minor, currency = "USD") =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(minor || 0) / 100);

// eslint-disable-next-line react-refresh/only-export-components
export const buildMyPlanView = ({ catalog, currentPlan, usage, entitlements, addons }) => {
  const products = catalog?.products || [];
  const planProduct = products.find((product) => product.id === currentPlan?.plan_id) || null;
  const capabilities = new Set(entitlements?.capabilities || []);
  const activeAddons = addons?.active || [];
  return {
    planProduct,
    state: currentPlan?.state || "none",
    source: currentPlan?.source || "",
    storage: usage?.storage || {},
    seats: usage?.workspace_seats || {},
    operations: usage?.operations || {},
    tokens: usage?.ai_tokens || {},
    activeAddons,
    futureAddons: (addons?.available || []).filter((product) => product.coming_soon),
    standardAddress: capabilities.has("standard_hosted_address"),
    brandedSubdomain: capabilities.has("branded_madar_subdomain"),
  };
};

export default function MyPlanPage() {
  const { direction, language } = useLanguage();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchJson(BILLING_API_ROUTES.catalog),
      fetchJson(BILLING_API_ROUTES.currentPlan),
      fetchJson(BILLING_API_ROUTES.usage),
      fetchJson(BILLING_API_ROUTES.entitlements),
      fetchJson(BILLING_API_ROUTES.addons),
    ])
      .then(([catalog, currentPlan, usage, entitlements, addons]) => {
        if (!cancelled) {
          setData({
            catalog: catalog.catalog,
            currentPlan,
            usage,
            entitlements: entitlements.entitlements,
            addons,
          });
        }
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError.message || "Could not load plan data.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const view = useMemo(() => buildMyPlanView(data || {}), [data]);
  const copy = language === "ar"
    ? {
        title: "خطتي",
        subtitle: "الخطة والميزات والاستخدام المعتمد لمساحة العمل الحالية.",
        loading: "جارٍ تحميل الخطة...",
        empty: "لا توجد خطة تجارية مفعلة. قد تحتاج السجلات القديمة إلى مراجعة يدوية.",
        review: "مراجعة الخطط",
        state: "حالة التفعيل",
        manual: "يتم التفعيل والدفع يدوياً. لا توجد بطاقة أو فاتورة أو تاريخ تجديد تلقائي.",
        storage: "التخزين",
        seats: "أعضاء مساحة العمل",
        addresses: "عناوين الموقع",
        standard: "العنوان القياسي",
        branded: "نطاق مدار الفرعي المميز",
        enabled: "مفعّل",
        unavailable: "غير مفعّل",
        ai: "رموز تحليلات الذكاء الاصطناعي",
        addons: "الإضافات النشطة",
        future: "إضافات قادمة",
        operations: "استخدام تشغيلي (ليس حداً تجارياً)",
      }
    : {
        title: "My Plan",
        subtitle: "Authoritative plan, entitlement, and usage data for this workspace.",
        loading: "Loading plan data...",
        empty: "No canonical plan is active. Legacy records may require manual review.",
        review: "Review plans",
        state: "Activation state",
        manual: "Activation and payment are reviewed manually. No card, invoice, or automatic renewal date is stored.",
        storage: "Hosted storage",
        seats: "Workspace members",
        addresses: "Website addresses",
        standard: "Standard hosted address",
        branded: "Branded Madar subdomain",
        enabled: "Enabled",
        unavailable: "Not active",
        ai: "AI analytics standard tokens",
        addons: "Active add-ons",
        future: "Coming-soon add-ons",
        operations: "Operational usage (not a commercial limit)",
      };

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
      {!loading && !error && (
        <>
          <article className="my-plan-current-card">
            <div className="my-plan-card-top">
              <div>
                <span>{copy.state}</span>
                <h2>{view.planProduct?.name || copy.empty}</h2>
              </div>
              <strong>{view.state}</strong>
            </div>
            {view.planProduct && (
              <p>{formatPrice(view.planProduct.price_minor, view.planProduct.currency)} / {view.planProduct.billing_interval}</p>
            )}
            <p role="note">{copy.manual}</p>
          </article>

          <div className="my-plan-usage-grid">
            <article className="my-plan-current-card">
              <h2>{copy.storage}</h2>
              <p>{formatBytes(view.storage.used_bytes)} used</p>
              <p>{formatBytes(view.storage.quota_bytes)} total allowance</p>
              <p>{formatBytes(Math.max(Number(view.storage.quota_bytes || 0) - Number(view.planProduct?.allowances?.storage_bytes || 0), 0))} added storage</p>
            </article>
            <article className="my-plan-current-card">
              <h2>{copy.seats}</h2>
              <p>{formatNumber(view.seats.used)} used</p>
              <p>{formatNumber(view.seats.included_and_added)} included and added</p>
            </article>
            <article className="my-plan-current-card">
              <h2>{copy.addresses}</h2>
              <p>{copy.standard}: {view.standardAddress ? copy.enabled : copy.unavailable}</p>
              <p>{copy.branded}: {view.brandedSubdomain ? copy.enabled : copy.unavailable}</p>
            </article>
            <article className="my-plan-current-card">
              <h2>{copy.ai}</h2>
              <p>{view.tokens.package || copy.unavailable}</p>
              <p>{formatNumber(view.tokens.included_standard_tokens)} included</p>
              <p>{formatNumber(view.tokens.purchased_pack_tokens)} purchased packs</p>
              <p>{formatNumber(view.tokens.used_standard_tokens)} used</p>
              <p>{formatNumber(view.tokens.reserved_standard_tokens)} reserved</p>
              <p>{formatNumber(view.tokens.remaining_standard_tokens)} remaining</p>
              {view.tokens.period_start && <p>{view.tokens.period_start} — {view.tokens.period_end} UTC</p>}
            </article>
          </div>

          <article className="my-plan-current-card">
            <h2>{copy.addons}</h2>
            {view.activeAddons.length
              ? view.activeAddons.map((addon) => <p key={addon.id}>{addon.addon_id} × {addon.quantity}</p>)
              : <p>{copy.unavailable}</p>}
          </article>

          <article className="my-plan-current-card">
            <h2>{copy.future}</h2>
            {view.futureAddons.map((addon) => (
              <button className="my-plan-button" type="button" disabled key={addon.id}>
                {addon.name}
              </button>
            ))}
          </article>

          <article className="my-plan-current-card">
            <h2>{copy.operations}</h2>
            <p>Forms created: {formatNumber(view.operations.forms_created)}</p>
            <p>Form submissions: {formatNumber(view.operations.form_submissions)}</p>
            <p>Reservation requests: {formatNumber(view.operations.reservation_requests)}</p>
            <button className="my-plan-button" type="button" onClick={() => navigate("/pricing")}>
              <ExternalLink size={16} /> {copy.review}
            </button>
          </article>
        </>
      )}
    </section>
  );
}
