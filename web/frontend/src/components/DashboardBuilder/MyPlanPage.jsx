import { useEffect, useMemo, useState } from "react";
import { CalendarClock, CreditCard, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { getPricingContent } from "../../content";
import { useLanguage } from "../../i18n";
import { BILLING_API_ROUTES } from "../../services/apiRoutes";
import { apiFetch, getApiUrl, readApiError, readApiErrorCode } from "../../utils/apiClient";
import { getEcommerceCacheScope, loadEcommerceAdminResource, readEcommerceAdminCacheSnapshot } from "./utils/ecommerceAdminCache";

const MODULE_IDS = ["forms", "website", "ecommerce"];

const fetchJson = async (path) => {
  const response = await apiFetch(getApiUrl(path), { method: "GET", cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(readApiError(data, "Could not load subscription data."));
  return data;
};

// Protection is reported by the database price resolver per price-book group;
// the UI only summarizes those flags and never derives eligibility itself.
const protectionStatus = (groups) => {
  if (!groups.length) return "none";
  const protectedCount = groups.filter((group) => group.grandfathered).length;
  if (protectedCount === groups.length) return "protected";
  if (protectedCount > 0) return "partial";
  return groups.every((group) => group.new_sales_active) ? "open" : "none";
};

// eslint-disable-next-line react-refresh/only-export-components
export const buildMyPlanView = ({ catalog, currentPlan, usage, entitlements, addons }) => {
  const products = catalog?.products || [];
  const assignedModules = currentPlan?.assigned_modules || [];
  const effectiveModules = entitlements?.effective_modules || [];
  const pricing = currentPlan?.pricing || entitlements?.pricing || null;
  const groups = pricing?.price_groups || [];
  const protectedUntil = groups
    .filter((group) => group.grandfathered && group.protection_valid_until)
    .map((group) => group.protection_valid_until)
    .sort((a, b) => new Date(a) - new Date(b))[0] || null;
  return {
    modules: MODULE_IDS.map((id) => products.find((product) => product.id === id)).filter(Boolean),
    assignedModules,
    effectiveModules,
    pricing,
    state: currentPlan?.commercial_access_state || currentPlan?.state || "none",
    paidThrough: currentPlan?.paid_through || currentPlan?.access_period?.valid_until || null,
    held: Boolean(currentPlan?.commercial_suspended_at),
    protectionEligible: groups.length > 0 && groups.every((group) => group.grandfathered),
    protectionStatus: protectionStatus(groups),
    protectedUntil,
    protectionBooks: [...new Set(groups.map((group) => group.price_book_id).filter(Boolean))],
    revision: currentPlan?.commercial_revision,
    schemaReady: currentPlan?.protection_contract_version === 145,
    storage: usage?.storage || {},
    seats: usage?.workspace_seats || {},
    activeAddons: addons?.active || [],
  };
};

const COPY = {
  ar: {
    title: "اشتراكي", subtitle: "الوحدات والسعر والتغطية وحماية سجل الأسعار لمساحة العمل الحالية.", loading: "جارٍ تحميل الاشتراك…",
    retry: "تعذر تحميل الاشتراك. يرجى المحاولة لاحقاً.", status: "حالة الوصول", modules: "الوحدات المشتركة", recurring: "السعر الشهري الحالي", paid: "مدفوع حتى",
    perMonth: "/ شهرياً", none: "لا توجد",
    states: { active: "فعّال", expired: "منتهٍ", inactive: "غير فعّال", suspended: "موقوف إدارياً", review_required: "قيد المراجعة", none: "لا يوجد اشتراك", legacy: "قيد المراجعة" },
    renewal: "التجديد والتغطية", held: "يوجد إيقاف إداري للوصول",
    protection: {
      protected: "سعر التأسيس محمي",
      partial: "سعر التأسيس محمي لبعض الوحدات فقط",
      open: "سجل أسعار الإطلاق الحالي",
      none: "لا توجد حماية فعّالة لسعر التأسيس",
    },
    protectionHelp: {
      protected: "يبقى السعر محمياً ما دامت التغطية المدفوعة مستمرة دون انقطاع.",
      partial: "الوحدات غير المحمية تُسعَّر من سجل الأسعار المفتوح للاشتراكات الجديدة.",
      open: "سجل الأسعار هذا ما زال مفتوحاً للاشتراكات الجديدة. التغطية المدفوعة المستمرة تحافظ على هذا السعر بعد إغلاقه.",
      none: "يُسعَّر الاشتراك من سجل الأسعار المفتوح للاشتراكات الجديدة.",
    },
    protectedUntil: "الحماية مؤكدة حتى",
    coverage: "يجب تأكيد فترة الدفع التالية قبل نهاية التغطية الحالية للمحافظة على الوصول وحماية السعر دون انقطاع.", expiration: "عند انتهاء التغطية ينتهي الوصول وحماية السعر. لا توجد فترة سماح أو استعادة تلقائية، ولا تُحذف بياناتك.",
    changes: "استعرض تغيير الوحدات", changesHelp: "اختر الوحدات المطلوبة لمعاينة سعر معتمد من الخادم. التغيير لا يتم تلقائياً.", quote: "معاينة السعر", quoting: "جارٍ طلب السعر…", proposed: "السعر الشهري المقترح", request: "تواصل لطلب التغيير",
    groupProtected: "سعر تأسيس محمي", groupOpen: "سجل الأسعار المفتوح حالياً",
    removed: "إزالة {modules} تنهي حماية سعر التأسيس لها. إعادة إضافتها لاحقاً تُسعَّر من سجل الأسعار المفتوح حينها.",
    added: "الوحدات المضافة تُسعَّر من سجل الأسعار المفتوح حالياً للاشتراكات الجديدة.",
    current: "الحالي", active: "فعّالة", assigned: "مشتركة", notAssigned: "غير مشتركة", unavailable: "غير متاح", schema: "إدارة الاشتراك غير متاحة حتى اكتمال ترقية المخطط التجاري.",
    quoteErrors: {
      commercial_price_book_unavailable: "لا يوجد سجل أسعار مفتوح حالياً لهذه الوحدات.",
      fallback: "معاينة السعر غير متاحة مؤقتاً.",
    },
  },
  en: {
    title: "My subscription", subtitle: "Modules, recurring price, paid coverage, and price-book protection for this workspace.", loading: "Loading subscription…",
    retry: "Could not load your subscription. Please try again later.", status: "Access status", modules: "Subscribed modules", recurring: "Current recurring price", paid: "Paid through",
    perMonth: "/ month", none: "None",
    states: { active: "Active", expired: "Expired", inactive: "Inactive", suspended: "On administrative hold", review_required: "Under review", none: "No subscription", legacy: "Under review" },
    renewal: "Renewal and coverage", held: "Administrative hold currently denies access",
    protection: {
      protected: "Founding price protected",
      partial: "Founding price protected for some modules",
      open: "Current launch price book",
      none: "No active founding-price protection",
    },
    protectionHelp: {
      protected: "Your price stays protected while confirmed paid coverage continues without interruption.",
      partial: "Modules without protection are priced from the price book open for new subscriptions.",
      open: "This price book is still open for new subscriptions. Continuous paid coverage keeps this price after it closes.",
      none: "Your subscription is priced from the price book open for new subscriptions.",
    },
    protectedUntil: "Protection confirmed through",
    coverage: "The next paid period must be confirmed before current coverage ends to preserve uninterrupted access and eligible price protection.", expiration: "At expiration, access and price protection end. There is no grace period or automatic recovery, and your tenant data is not deleted.",
    changes: "Explore module changes", changesHelp: "Select the modules you want and preview a server-authoritative price. Nothing changes automatically.", quote: "Preview price", quoting: "Getting price…", proposed: "Proposed monthly price", request: "Contact us to request change",
    groupProtected: "Protected founding price", groupOpen: "Price book currently open",
    removed: "Removing {modules} ends their founding-price protection. Adding them back later uses the price book open at that time.",
    added: "Added modules are priced from the price book currently open for new subscriptions.",
    current: "Current", active: "Effective", assigned: "Subscribed", notAssigned: "Not subscribed", unavailable: "Unavailable", schema: "Subscription management is unavailable until the commercial schema upgrade is complete.",
    quoteErrors: {
      commercial_price_book_unavailable: "No price book is currently open for this module selection.",
      fallback: "Price previews are temporarily unavailable.",
    },
  },
};

export default function MyPlanPage({ user }) {
  const { direction, language } = useLanguage();
  const navigate = useNavigate();
  const cacheScope = getEcommerceCacheScope(user);
  const initialSnapshot = useMemo(() => readEcommerceAdminCacheSnapshot(cacheScope, "my-plan"), [cacheScope]);
  const [data, setData] = useState(() => initialSnapshot?.data || null);
  const [loading, setLoading] = useState(() => !initialSnapshot);
  const [error, setError] = useState("");
  const [selection, setSelection] = useState(() => initialSnapshot?.data?.currentPlan?.assigned_modules || []);
  const [quote, setQuote] = useState(null);
  const [quoteState, setQuoteState] = useState("idle");
  const [quoteError, setQuoteError] = useState("");

  useEffect(() => {
    let cancelled = false;
    loadEcommerceAdminResource(cacheScope, "my-plan", async () => {
      const [catalog, currentPlan, usage, entitlements, addons] = await Promise.all([
        fetchJson(BILLING_API_ROUTES.catalog), fetchJson(BILLING_API_ROUTES.currentPlan),
        fetchJson(BILLING_API_ROUTES.usage), fetchJson(BILLING_API_ROUTES.entitlements), fetchJson(BILLING_API_ROUTES.addons),
      ]);
      return { catalog: catalog.catalog, currentPlan, usage, entitlements: entitlements.entitlements, addons };
    }, { force: Boolean(initialSnapshot?.isStale) })
      .then((nextData) => { if (!cancelled) { setData(nextData); setSelection(nextData.currentPlan?.assigned_modules || []); setError(""); } })
      .catch((loadError) => { if (!cancelled) setError(loadError.message || "Could not load subscription data."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [cacheScope, initialSnapshot?.isStale]);

  const view = useMemo(() => buildMyPlanView(data || {}), [data]);
  const isArabic = language === "ar";
  const c = isArabic ? COPY.ar : COPY.en;
  const moduleCopy = getPricingContent(isArabic ? "ar" : "en").modules;
  const names = Object.fromEntries(MODULE_IDS.map((id) => [id, moduleCopy[id].name]));
  const listModules = (ids) => (ids || []).map((id) => names[id] || id).join(isArabic ? " و" : ", ");
  const formatMoney = (minor, currency = "USD") => Number.isInteger(minor)
    ? new Intl.NumberFormat(isArabic ? "ar" : "en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(minor / 100)
    : c.unavailable;
  const formatDate = (value) => value
    ? new Intl.DateTimeFormat(isArabic ? "ar" : "en-US", { dateStyle: "long", timeStyle: "short" }).format(new Date(value))
    : c.unavailable;
  const stateLabel = c.states[view.state] || c.unavailable;
  const removedModules = quote?.removed_module_ids || [];
  const addedModules = quote ? (quote.pricing?.module_ids || []).filter((id) => !view.assignedModules.includes(id)) : [];

  const toggleModule = (id) => {
    setSelection((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
    setQuote(null); setQuoteState("idle"); setQuoteError("");
  };
  const previewQuote = async () => {
    if (!selection.length) return;
    setQuoteState("loading"); setQuoteError(""); setQuote(null);
    try {
      const response = await apiFetch(getApiUrl(BILLING_API_ROUTES.moduleQuote), {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ module_ids: selection }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(c.quoteErrors[readApiErrorCode(result)] || c.quoteErrors.fallback);
      }
      setQuote(result.quote); setQuoteState("success");
    } catch (quoteFailure) { setQuoteError(quoteFailure.message || c.quoteErrors.fallback); setQuoteState("error"); }
  };

  return <main className="my-plan-page" dir={direction}>
    <header className="my-plan-header app-page-intro"><div><h1>{c.title}</h1><p>{c.subtitle}</p></div></header>
    {loading && <div className="my-plan-current-card" role="status">{c.loading}</div>}
    {!loading && error && <div className="my-plan-current-card" role="alert">{c.retry}</div>}
    {!loading && !error && <>
      <section className="my-plan-overview" aria-label={c.status}>
        <article className="my-plan-current-card"><div className="my-plan-card-top"><div><span>{c.status}</span><h2>{stateLabel}</h2></div>{view.held && <strong>{c.held}</strong>}</div>
          <div className="my-plan-price-row"><strong>{formatMoney(view.pricing?.recurring_minor, view.pricing?.currency)}</strong><span>{c.perMonth}</span></div>
          <div className="my-plan-meta-grid"><div><span>{c.paid}</span><strong>{formatDate(view.paidThrough)}</strong></div><div><span>{c.recurring}</span><strong>{formatMoney(view.pricing?.recurring_minor, view.pricing?.currency)}</strong></div><div><span>{c.modules}</span><strong>{listModules(view.assignedModules) || c.none}</strong></div></div>
        </article>
        <article className="my-plan-recommendation-card"><ShieldCheck aria-hidden="true" /><h2>{c.protection[view.protectionStatus]}</h2><p>{c.protectionHelp[view.protectionStatus]}</p>{view.protectedUntil && <p>{c.protectedUntil} {formatDate(view.protectedUntil)}</p>}<p>{c.coverage}</p></article>
      </section>

      <section className="my-plan-section"><div className="my-plan-section-header"><div><h2>{c.modules}</h2><p>{c.expiration}</p></div></div>
        <div className="my-plan-usage-grid">{MODULE_IDS.map((id) => <article className="my-plan-usage-card" key={id}><div className="my-plan-usage-top"><strong>{names[id]}</strong><em>{view.effectiveModules.includes(id) ? c.active : view.assignedModules.includes(id) ? c.assigned : c.notAssigned}</em></div></article>)}</div>
      </section>

      <section className="my-plan-section"><div className="my-plan-section-header"><div><h2>{c.renewal}</h2><p>{c.coverage}</p></div><CalendarClock aria-hidden="true" /></div><article className="my-plan-current-card"><p>{c.expiration}</p></article></section>

      <section className="my-plan-section"><div className="my-plan-section-header"><div><h2>{c.changes}</h2><p>{c.changesHelp}</p></div></div>
        {!view.schemaReady ? <div className="my-plan-current-card" role="alert">{c.schema}</div> : <div className="my-plan-module-layout"><div className="my-plan-module-list">{view.modules.map((module) => <button type="button" className={`my-plan-module-card ${selection.includes(module.id) ? "selected" : ""}`} aria-pressed={selection.includes(module.id)} key={module.id} onClick={() => toggleModule(module.id)}><span><strong>{names[module.id]}</strong><p>{moduleCopy[module.id]?.summary || module.summary}</p></span><em aria-hidden="true">{selection.includes(module.id) ? "✓" : "+"}</em></button>)}</div>
          <aside className="my-plan-module-detail"><h3>{c.changes}</h3><p>{selection.map((id) => names[id]).join(" + ") || c.unavailable}</p><button className="my-plan-button primary" type="button" disabled={!selection.length || quoteState === "loading"} onClick={previewQuote}><CreditCard size={17} />{quoteState === "loading" ? c.quoting : c.quote}</button>
            <div aria-live="polite">
              {quote && <div className="my-plan-module-price"><span>{c.proposed}</span><strong>{formatMoney(quote.pricing?.recurring_minor, quote.pricing?.currency)}</strong></div>}
              {quote && (quote.pricing?.price_groups || []).map((group) => <p key={group.price_book_id}>{listModules(group.module_ids)} · {formatMoney(group.recurring_minor, quote.pricing?.currency)} · {group.grandfathered ? c.groupProtected : c.groupOpen}</p>)}
              {quote && addedModules.length > 0 && <p>{c.added}</p>}
              {quote && removedModules.length > 0 && <p role="status">{c.removed.replace("{modules}", listModules(removedModules))}</p>}
              {quoteError && <p role="alert">{quoteError}</p>}
            </div>
            {quote && <button className="my-plan-button secondary" type="button" onClick={() => navigate("/contact")}>{c.request}</button>}</aside>
        </div>}
      </section>
    </>}
  </main>;
}
