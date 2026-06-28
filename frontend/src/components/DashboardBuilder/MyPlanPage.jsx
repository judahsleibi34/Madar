import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CreditCard, ExternalLink, Lock, Settings, Unlock } from "lucide-react";
import { getMyPlanContent } from "../../content";

const MODULE_PATHS = {
  website: "/page-builder",
  forms: "/builder-responses",
  requests: "/builder-responses",
  data: "/builder-data",
  reports: "/builder-data",
  workflows: "/page-builder",
};

const PLAN_PRICES = {
  basic: "$19",
  starter: "$29",
  premium: "$59",
  pro: "$99",
  full_platform: "$99",
};

const PLAN_LIMITS = {
  basic: { websites: 1, forms: 5, submissions: 500, users: 2 },
  starter: { websites: 3, forms: 25, submissions: 5000, users: 3 },
  premium: { websites: 8, forms: 75, submissions: 15000, users: 15 },
  pro: { websites: 20, forms: 200, submissions: 50000, users: 50 },
  full_platform: { websites: 20, forms: 200, submissions: 50000, users: 50 },
};

const BUILDER_MODULE_IDS = new Set(["website", "forms", "data", "reports"]);

function titleCase(value) {
  return String(value || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getActiveBuilderIds(user) {
  if (user?.subscription_type === "full_platform") {
    return new Set(["website", "forms", "requests", "data", "reports", "workflows"]);
  }

  const activeFeatures = Array.isArray(user?.features)
    ? user.features.filter(
        (feature) =>
          (feature.payment_status || user?.payment_status) === "active"
      )
    : [];

  const featureIds = activeFeatures
    .map((feature) => feature.builder_type)
    .filter(Boolean);

  if (featureIds.length > 0) {
    const ids = new Set(featureIds);
    if (ids.has("forms")) ids.add("requests");
    return ids;
  }

  if (user?.builder_type) {
    return new Set([user.builder_type]);
  }

  return new Set(["website", "forms", "requests"]);
}

function getPlanName(user, fallback) {
  if (user?.subscription_type === "full_platform") return "Full platform";
  if (user?.plan) return titleCase(user.plan);
  if (user?.builder_type) return `${titleCase(user.builder_type)} builder`;
  return fallback;
}

function getUsage(content, user) {
  const planKey =
    user?.subscription_type === "full_platform"
      ? "full_platform"
      : user?.plan || "starter";
  const limits = PLAN_LIMITS[planKey] || PLAN_LIMITS.starter;

  return content.usage.map((item, index) => {
    if (index === 0) return { ...item, max: limits.websites };
    if (index === 1) return { ...item, max: limits.forms };
    if (index === 2) return { ...item, max: limits.submissions };
    if (index === 3) return { ...item, max: limits.users };
    return item;
  });
}

function getUsageTone(percent) {
  if (percent >= 90) return "danger";
  if (percent >= 70) return "warning";
  return "";
}

export default function MyPlanPage({ lang = "en", user }) {
  const activeLang = lang === "ar" ? "ar" : "en";
  const isArabic = activeLang === "ar";
  const content = getMyPlanContent(activeLang);
  const navigate = useNavigate();
  const enabledModuleIds = useMemo(() => getActiveBuilderIds(user), [user]);

  const modules = useMemo(
    () =>
      content.modules.map((module) => ({
        ...module,
        enabled:
          module.enabled ||
          enabledModuleIds.has(module.id) ||
          (enabledModuleIds.has("forms") && module.id === "requests") ||
          (user?.subscription_type === "full_platform" &&
            BUILDER_MODULE_IDS.has(module.id)),
      })),
    [content.modules, enabledModuleIds, user?.subscription_type]
  );

  const [selectedModuleId, setSelectedModuleId] = useState(
    modules[0]?.id || ""
  );
  const selectedModule =
    modules.find((module) => module.id === selectedModuleId) || modules[0];

  const plan = {
    ...content.plan,
    name: getPlanName(user, content.plan.name),
    status: user?.payment_status ? titleCase(user.payment_status) : content.plan.status,
    price:
      PLAN_PRICES[
        user?.subscription_type === "full_platform"
          ? "full_platform"
          : user?.plan
      ] || content.plan.price,
  };
  const usage = getUsage(content, user);

  const openSelectedModule = () => {
    if (!selectedModule) return;
    navigate(selectedModule.enabled ? MODULE_PATHS[selectedModule.id] || "/dashboard" : "/pricing");
  };

  return (
    <section className="my-plan-page" dir={isArabic ? "rtl" : "ltr"}>
      <header className="my-plan-header">
        <div>
          <span className="my-plan-eyebrow">{content.eyebrow}</span>
          <h1>{content.title}</h1>
          <p>{content.subtitle}</p>
        </div>

        <div className="my-plan-actions">
          <button
            type="button"
            className="my-plan-button secondary"
            onClick={() => navigate("/settings")}
          >
            <Settings size={17} />
            {content.manageBilling}
          </button>
          <button
            type="button"
            className="my-plan-button primary"
            onClick={() => navigate("/pricing")}
          >
            <CreditCard size={17} />
            {content.upgradePlan}
          </button>
        </div>
      </header>

      <div className="my-plan-overview">
        <article className="my-plan-current-card">
          <div className="my-plan-card-top">
            <div>
              <span>{content.currentPlan}</span>
              <h2>{plan.name}</h2>
            </div>
            <strong>{plan.status}</strong>
          </div>

          <p>{plan.description}</p>

          <div className="my-plan-price-row">
            <strong>{plan.price}</strong>
            <span>{content.perMonth}</span>
          </div>

          <div className="my-plan-meta-grid">
            <div>
              <span>{content.billingCycle}</span>
              <strong>{plan.billingCycle}</strong>
            </div>
            <div>
              <span>{content.renewsOn}</span>
              <strong>{plan.renewsOn}</strong>
            </div>
            <div>
              <span>{content.users}</span>
              <strong>{plan.users}</strong>
            </div>
            <div>
              <span>{content.workspace}</span>
              <strong>{plan.workspace}</strong>
            </div>
          </div>
        </article>

        <aside className="my-plan-recommendation-card">
          <span>{content.recommendationLabel}</span>
          <h2>{content.recommendationTitle}</h2>
          <p>{content.recommendationText}</p>
          <ul>
            {content.recommendationPoints.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
          <button
            type="button"
            className="my-plan-button primary"
            onClick={() => navigate("/pricing")}
          >
            <ExternalLink size={17} />
            {content.viewUpgrade}
          </button>
        </aside>
      </div>

      <section className="my-plan-section">
        <div className="my-plan-section-header">
          <div>
            <span className="my-plan-eyebrow">{content.usageLabel}</span>
            <h2>{content.usageTitle}</h2>
          </div>
          <p>{content.usageSubtitle}</p>
        </div>

        <div className="my-plan-usage-grid">
          {usage.map((item) => {
            const percent = Math.min(100, Math.round((item.value / item.max) * 100));

            return (
              <article
                className={`my-plan-usage-card ${getUsageTone(percent)}`}
                key={item.label}
              >
                <div className="my-plan-usage-top">
                  <div>
                    <span>{item.label}</span>
                    <strong>
                      {item.value.toLocaleString()} / {item.max.toLocaleString()}
                    </strong>
                  </div>
                  <em>{percent}%</em>
                </div>
                <div className="my-plan-progress" aria-hidden="true">
                  <span style={{ width: `${percent}%` }} />
                </div>
                <p>{item.note}</p>
              </article>
            );
          })}
        </div>
      </section>

      <section className="my-plan-section">
        <div className="my-plan-section-header">
          <div>
            <span className="my-plan-eyebrow">{content.modulesLabel}</span>
            <h2>{content.modulesTitle}</h2>
          </div>
          <p>{content.modulesSubtitle}</p>
        </div>

        <div className="my-plan-module-layout">
          <div className="my-plan-module-list">
            {modules.map((module) => (
              <button
                type="button"
                key={module.id}
                className={`my-plan-module-card ${
                  module.enabled ? "" : "locked"
                } ${selectedModule?.id === module.id ? "selected" : ""}`}
                onClick={() => setSelectedModuleId(module.id)}
              >
                <div>
                  <span>
                    {module.enabled ? content.enabled : content.locked}
                  </span>
                  <strong>{module.name}</strong>
                  <p>{module.description}</p>
                </div>
                <em>{module.price}</em>
              </button>
            ))}
          </div>

          {selectedModule && (
            <aside className="my-plan-module-detail">
              <span className="my-plan-eyebrow">
                {selectedModule.enabled
                  ? content.enabledModule
                  : content.lockedModule}
              </span>
              <h3>{selectedModule.name}</h3>
              <p>{selectedModule.value}</p>

              <div className="my-plan-module-price">
                <span>{content.modulePrice}</span>
                <strong>{selectedModule.price}</strong>
              </div>

              <button
                type="button"
                className={`my-plan-button ${
                  selectedModule.enabled ? "secondary" : "primary"
                }`}
                onClick={openSelectedModule}
              >
                {selectedModule.enabled ? (
                  <Unlock size={17} />
                ) : (
                  <Lock size={17} />
                )}
                {selectedModule.enabled
                  ? content.openModule
                  : content.unlockModule}
              </button>
            </aside>
          )}
        </div>
      </section>
    </section>
  );
}
