import { useEffect, useMemo, useState } from "react";
import { BadgeCheck, CheckCircle2, Clock3, Info } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { getPricingContent } from "../../content";
import { DASHBOARD_ROUTES, PUBLIC_ROUTES } from "../../config/routes";
import { BILLING_API_ROUTES } from "../../services/apiRoutes";
import { apiFetch, getApiUrl, readApiError } from "../../utils/apiClient";
import SubscriptionStatusModal from "./SubscriptionStatusModal";

const formatPrice = (minor, currency, locale = "en-US") =>
  new Intl.NumberFormat(locale, {
    style: "currency",
    currency: currency || "USD",
    maximumFractionDigits: 0,
  }).format(Number(minor || 0) / 100);

const formatStorage = (bytes) => `${Math.round(Number(bytes || 0) / 1024 ** 3)} GB`;

const CARD_FEATURE_KEYS = {
  website: ["reservation_system"],
  business: ["reservation_system", "cv_reranker"],
};

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
  const availableAddons = useMemo(
    () => addons.filter((addon) => !addon.coming_soon && addon.price_minor != null),
    [addons]
  );
  const upcomingAddons = useMemo(
    () => addons.filter((addon) => addon.coming_soon || addon.price_minor == null),
    [addons]
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
        </div>
      </section>


      {loading && <section className="pricing-base-section" role="status">{t.loading}</section>}
      {!loading && error && <section className="pricing-base-section" role="alert">{error}</section>}

      {!loading && !error && (
        <section className="pricing-base-section">
          <div className="pricing-catalog-heading">
            <div>
              <span>{t.eyebrow}</span>
              <h2>{t.plansTitle}</h2>
            </div>
          </div>

          <div className="pricing-plan-strip pricing-comparison-grid">
            {plans.map((plan) => {
              const copy = t.plans[plan.id];
              const recommended = plan.id === "business";
              const visibleFeatureKeys = [
                ...new Set([...(plan.public_feature_keys || []), ...(CARD_FEATURE_KEYS[plan.id] || [])]),
              ];
              return (
                <article className={`pricing-mini-plan pricing-catalog-plan ${recommended ? "is-selected" : ""}`} key={plan.id}>
                  <header className="pricing-catalog-plan-header">
                    <div>
                      <span>{t.planLabel}</span>
                      {recommended && <em><BadgeCheck size={14} aria-hidden="true" />{t.recommended}</em>}
                    </div>
                    <h3>{copy?.name || plan.name}</h3>
                    <p>{copy?.summary || plan.summary}</p>
                  </header>
                  <div className="pricing-catalog-price">
                    <strong>{formatPrice(plan.price_minor, plan.currency, activeLang === "ar" ? "ar" : "en-US")}</strong>
                    <span>{t.perMonth}</span>
                  </div>
                  <div className="pricing-includes-label">{t.includedTitle}</div>
                  <ul className="pricing-feature-list">
                    {visibleFeatureKeys.map((featureKey) => (
                      <li className="included" key={featureKey}>
                        <CheckCircle2 size={15} aria-hidden="true" />
                        <span>{t.featureLabels[featureKey] || featureKey}</span>
                      </li>
                    ))}
                    <li className="included"><CheckCircle2 size={15} aria-hidden="true" /><span>{formatStorage(plan.allowances?.storage_bytes)} {t.hostedStorage}</span></li>
                    <li className="included"><CheckCircle2 size={15} aria-hidden="true" /><span>{t.oneOperator}</span></li>
                  </ul>
                  <footer>
                    <button className="pricing-plan-button primary" type="button" disabled={submittingId === plan.id} onClick={() => requestPlan(plan)}>
                      {submittingId === plan.id ? t.saving : t.requestPlan}
                    </button>
                  </footer>
                </article>
              );
            })}
          </div>

          {addons.length > 0 && (
            <section className="pricing-compare pricing-addons-section" aria-labelledby="pricing-addons-title">
              <div className="pricing-addons-heading">
                <div><span>{t.addonsLabel}</span><h2 id="pricing-addons-title">{t.addonsTitle}</h2></div>
              </div>

              {availableAddons.length > 0 && (
                <div className="pricing-addon-group">
                  <div className="pricing-addon-group-heading"><h3>{t.availableAddons}</h3></div>
                  <div className="pricing-addon-grid">
                    {availableAddons.map((addon) => (
                      <article className="pricing-addon-card is-available" key={addon.id}>
                        <div className="pricing-addon-card-heading">
                          <span className="pricing-addon-status"><CheckCircle2 size={14} aria-hidden="true" />{t.availableNow}</span>
                          <h4>{t.addons[addon.id]?.name || addon.name}</h4>
                        </div>
                        <div className="pricing-addon-price">
                          <strong>{formatPrice(addon.price_minor, addon.currency, activeLang === "ar" ? "ar" : "en-US")}</strong>
                          {addon.billing_interval === "month" && <span>{t.perMonth}</span>}
                        </div>
                        <p>{t.addons[addon.id]?.summary || addon.summary}</p>
                      </article>
                    ))}
                  </div>
                </div>
              )}

              {upcomingAddons.length > 0 && (
                <div className="pricing-addon-group is-upcoming">
                  <div className="pricing-addon-group-heading"><h3>{t.upcomingAddons}</h3></div>
                  <div className="pricing-addon-grid pricing-upcoming-grid">
                    {upcomingAddons.map((addon) => (
                      <article className="pricing-addon-card is-upcoming" key={addon.id}>
                        <Clock3 size={18} aria-hidden="true" />
                        <div><h4>{t.addons[addon.id]?.name || addon.name}</h4><p>{t.addons[addon.id]?.summary || addon.summary}</p></div>
                        <span className="pricing-addon-coming-soon">{t.comingSoon}</span>
                      </article>
                    ))}
                  </div>
                </div>
              )}
            </section>
          )}

          <aside className="pricing-storage-callout" role="note">
            <Info size={20} aria-hidden="true" />
            <div><strong>{t.goodToKnow}</strong><ul><li>{t.fairUse}</li><li>{t.addressNote}</li><li>{t.exclusions}</li></ul></div>
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
