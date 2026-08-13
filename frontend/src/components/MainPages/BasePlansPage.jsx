import { useEffect, useMemo, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { getPricingContent } from "../../content";
import { DASHBOARD_ROUTES, PUBLIC_ROUTES } from "../../config/routes";
import { BILLING_API_ROUTES } from "../../services/apiRoutes";
import { apiFetch, getApiUrl, readApiError } from "../../utils/apiClient";
import SubscriptionStatusModal from "./SubscriptionStatusModal";

const formatPrice = (minor, currency) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: currency || "USD",
    maximumFractionDigits: 0,
  }).format(Number(minor || 0) / 100);

const formatStorage = (bytes) => `${Math.round(Number(bytes || 0) / 1024 ** 3)} GB`;

export default function BasePlansPage({ lang = "en" }) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const t = getPricingContent(activeLang);
  const navigate = useNavigate();
  const location = useLocation();
  const [catalog, setCatalog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submittingId, setSubmittingId] = useState("");
  const [modalState, setModalState] = useState({ open: false, type: "success", message: "" });

  useEffect(() => {
    let cancelled = false;
    apiFetch(getApiUrl(BILLING_API_ROUTES.catalog), { method: "GET", cache: "no-store" })
      .then(async (response) => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(readApiError(data, t.catalogError));
        if (!cancelled) setCatalog(data.catalog);
      })
      .catch((loadError) => {
        if (!cancelled) setError(loadError.message || t.catalogError);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [t.catalogError]);

  const plans = useMemo(
    () => (catalog?.products || []).filter((product) => product.type === "base_plan"),
    [catalog]
  );
  const addons = useMemo(
    () => (catalog?.products || []).filter((product) =>
      ["add_on", "token_pack"].includes(product.type)
    ),
    [catalog]
  );

  const requestPlan = async (plan) => {
    setSubmittingId(plan.id);
    try {
      const response = await apiFetch(getApiUrl(BILLING_API_ROUTES.planRequest), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan_id: plan.id }),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setModalState({
          open: true,
          type: response.status === 401 ? "login" : "error",
          message: readApiError(data, t.requestError),
        });
        return;
      }
      setModalState({
        open: true,
        type: "success",
        message: data.message || t.requestSaved,
      });
    } catch {
      setModalState({ open: true, type: "error", message: t.requestError });
    } finally {
      setSubmittingId("");
    }
  };

  const closeModal = () => {
    const type = modalState.type;
    setModalState({ open: false, type: "success", message: "" });
    if (type === "success") navigate(DASHBOARD_ROUTES.myPlan);
    if (type === "login") navigate(PUBLIC_ROUTES.login);
  };

  return (
    <main className="pricing-page" dir={activeLang === "ar" ? "rtl" : "ltr"}>
      <section className="pricing-inner-header">
        {location.pathname !== PUBLIC_ROUTES.pricing && (
          <button className="pricing-back-button" type="button" onClick={() => navigate(PUBLIC_ROUTES.pricing)}>
            {t.back}
          </button>
        )}
        <div className="pricing-section-heading">
          <span className="pricing-eyebrow">{t.eyebrow}</span>
          <h1>{t.title}</h1>
          <p>{t.subtitle}</p>
          <p role="note"><strong>{t.manualActivation}</strong></p>
        </div>
      </section>

      {loading && <section className="pricing-base-section" role="status">{t.loading}</section>}
      {!loading && error && <section className="pricing-base-section" role="alert">{error}</section>}

      {!loading && !error && (
        <section className="pricing-base-section">
          <div className="pricing-plan-strip">
            {plans.map((plan) => {
              const copy = t.plans[plan.id];
              return (
                <article className={`pricing-mini-plan ${plan.id === "business" ? "is-selected" : ""}`} key={plan.id}>
                  <span>{copy?.name || plan.name}</span>
                  <strong>{formatPrice(plan.price_minor, plan.currency)}{t.perMonth}</strong>
                  <small>{copy?.summary || plan.summary}</small>
                  <ul className="pricing-feature-list">
                    {(plan.public_feature_keys || []).map((featureKey) => (
                      <li className="included" key={featureKey}>
                        <CheckCircle2 size={15} aria-hidden="true" /> {t.featureLabels[featureKey] || featureKey}
                      </li>
                    ))}
                    <li className="included">
                      <CheckCircle2 size={15} aria-hidden="true" />
                      {formatStorage(plan.allowances?.storage_bytes)} {t.hostedStorage}
                    </li>
                    <li className="included">
                      <CheckCircle2 size={15} aria-hidden="true" /> {t.oneOperator}
                    </li>
                  </ul>
                  <button
                    className="pricing-plan-button primary"
                    type="button"
                    disabled={submittingId === plan.id}
                    onClick={() => requestPlan(plan)}
                  >
                    {submittingId === plan.id ? t.saving : t.requestPlan}
                  </button>
                </article>
              );
            })}
          </div>

          <section className="pricing-compare" aria-labelledby="pricing-addons-title">
            <h2 id="pricing-addons-title">{t.addonsTitle}</h2>
            <div className="pricing-plan-strip">
              {addons.map((addon) => (
                <article className="pricing-mini-plan" key={addon.id}>
                  <span>{t.addons[addon.id]?.name || addon.name}</span>
                  <strong>
                    {addon.price_minor == null
                      ? t.comingSoon
                      : `${formatPrice(addon.price_minor, addon.currency)}${
                          addon.billing_interval === "month" ? t.perMonth : ""
                        }`}
                  </strong>
                  <small>{t.addons[addon.id]?.summary || addon.summary}</small>
                  {addon.coming_soon && <small role="note">{t.comingSoon}</small>}
                </article>
              ))}
            </div>
          </section>

          <aside className="pricing-storage-callout" role="note">
            <p>{t.fairUse}</p>
            <p>{t.addressNote}</p>
            <p>{t.exclusions}</p>
          </aside>
        </section>
      )}

      <SubscriptionStatusModal
        open={modalState.open}
        type={modalState.type}
        lang={activeLang}
        message={modalState.message}
        onConfirm={closeModal}
      />
    </main>
  );
}
