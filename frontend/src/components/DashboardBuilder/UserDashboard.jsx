import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ArrowUpRight,
  BarChart3,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  CreditCard,
  Database,
  FileText,
  Globe2,
  Grid2X2,
  MessageSquare,
  PieChart,
  Rocket,
  Settings,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

const BUILDER_FEATURES = [
  {
    id: "website",
    icon: Globe2,
    path: "/page-builder",
  },
  {
    id: "forms",
    icon: ClipboardList,
    path: "/builder-responses",
  },
  {
    id: "quiz",
    icon: CheckCircle2,
    path: "/page-builder",
  },
  {
    id: "reservation",
    icon: CalendarClock,
    path: "/page-builder",
  },
  {
    id: "reports",
    icon: FileText,
    path: "/builder-data",
  },
  {
    id: "data",
    icon: Database,
    path: "/builder-data",
  },
];

const usageItems = [
  { key: "projects", value: 1, max: 5 },
  { key: "users", value: 3, max: 10 },
  { key: "responses", value: 128, max: 1000 },
  { key: "storage", value: 2.4, max: 10, suffix: "GB" },
];

function toTitleCase(value) {
  return value.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatFallbackValue(value) {
  return toTitleCase(String(value || "").replace(/_/g, " "));
}

function formatPlanLabel(plan, subscriptionType, builderType, t) {
  if (plan) {
    return t(`userDashboard.plans.${plan}`, {
      defaultValue: formatFallbackValue(plan),
    });
  }

  if (subscriptionType === "full_platform") {
    return t("userDashboard.plans.fullPlatform");
  }

  if (builderType) {
    return t("userDashboard.plans.builder", {
      builder: t(`userDashboard.builderTypes.${builderType}`, {
        defaultValue: formatFallbackValue(builderType),
      }),
    });
  }

  return t("userDashboard.plans.workspace");
}

function formatStatus(status, t) {
  if (!status) return t("userDashboard.status.pending");

  return t(`userDashboard.status.${status}`, {
    defaultValue: formatFallbackValue(status),
  });
}

export default function UserDashboard({ user }) {
  const { t } = useTranslation(["dashboard"]);
  const navigate = useNavigate();

  const displayName =
    user?.first_name || user?.name || user?.email || t("user.fallbackName");
  const features = Array.isArray(user?.features) ? user.features : [];
  const subscriptionType = user?.subscription_type || "";
  const activePlan = user?.plan || "";
  const activeBuilderType = user?.builder_type || "";
  const paymentStatus = user?.payment_status || "";

  const enabledBuilderIds = useMemo(() => {
    if (subscriptionType === "full_platform") {
      return new Set(BUILDER_FEATURES.map((feature) => feature.id));
    }

    const activeFeatures = features.filter(
      (feature) => (feature.payment_status || paymentStatus) === "active"
    );
    const builderIds = activeFeatures
      .map((feature) => feature.builder_type)
      .filter(Boolean);

    if (builderIds.length > 0) {
      return new Set(builderIds);
    }

    if (activeBuilderType) {
      return new Set([activeBuilderType]);
    }

    return new Set(["website", "forms", "data"]);
  }, [activeBuilderType, features, paymentStatus, subscriptionType]);

  const enabledCount = BUILDER_FEATURES.filter((feature) =>
    enabledBuilderIds.has(feature.id)
  ).length;
  const planLabel = formatPlanLabel(
    activePlan,
    subscriptionType,
    activeBuilderType,
    t
  );
  const statusLabel = formatStatus(paymentStatus, t);

  const summaryCards = [
    {
      label: t("userDashboard.summary.currentPlan"),
      value: planLabel,
      note: statusLabel,
      icon: CreditCard,
      tone: "red",
    },
    {
      label: t("userDashboard.summary.enabledBuilders"),
      value: `${enabledCount}/${BUILDER_FEATURES.length}`,
      note:
        subscriptionType === "full_platform"
          ? t("userDashboard.summary.fullPlatformAccess")
          : t("userDashboard.summary.activeTools"),
      icon: Grid2X2,
      tone: "plum",
    },
    {
      label: t("userDashboard.summary.responses"),
      value: "128",
      note: t("userDashboard.summary.fromWebsiteForms"),
      icon: MessageSquare,
      tone: "navy",
    },
    {
      label: t("userDashboard.summary.dataWorkspace"),
      value: enabledBuilderIds.has("data")
        ? t("userDashboard.summary.ready")
        : t("userDashboard.summary.addOn"),
      note: t("userDashboard.summary.reportsAndImports"),
      icon: BarChart3,
      tone: "red",
    },
  ];

  const recentActivity = [
    {
      title: t("userDashboard.activity.websiteReadyTitle"),
      detail: t("userDashboard.activity.websiteReadyDetail"),
      icon: Globe2,
    },
    {
      title: t("userDashboard.activity.submissionsActiveTitle"),
      detail: t("userDashboard.activity.submissionsActiveDetail"),
      icon: ClipboardList,
    },
    {
      title: t("userDashboard.activity.dataLogsTitle"),
      detail: t("userDashboard.activity.dataLogsDetail"),
      icon: Database,
    },
  ];

  return (
    <section className="user-dashboard-page dashboard-page">
      <header className="user-dashboard-header">
        <div>
          <span className="user-dashboard-kicker">
            {t("userDashboard.header.kicker")}
          </span>
          <h1>{t("userDashboard.header.title", { name: displayName })}</h1>
          <p>{t("userDashboard.header.subtitle")}</p>
        </div>

        <div className="user-dashboard-header-actions">
          <button type="button" onClick={() => navigate("/settings")}>
            <Settings size={18} />
            {t("userDashboard.actions.settings")}
          </button>
          <button type="button" className="is-primary" onClick={() => navigate("/page-builder")}>
            <Rocket size={18} />
            {t("userDashboard.actions.openBuilder")}
          </button>
        </div>
      </header>

      <section
        className="user-dashboard-summary"
        aria-label={t("userDashboard.summary.aria")}
      >
        {summaryCards.map((card) => {
          const Icon = card.icon;

          return (
            <article className={`user-dashboard-stat tone-${card.tone}`} key={card.label}>
              <div>
                <span>{card.label}</span>
                <strong>{card.value}</strong>
                <small>{card.note}</small>
              </div>
              <span className="user-dashboard-stat-icon" aria-hidden="true">
                <Icon size={22} />
              </span>
            </article>
          );
        })}
      </section>

      <section className="user-dashboard-main-grid">
        <article className="user-dashboard-panel user-dashboard-builders-panel">
          <div className="user-dashboard-panel-header">
            <div>
              <span className="user-dashboard-kicker">
                {t("userDashboard.builders.kicker")}
              </span>
              <h2>{t("userDashboard.builders.title")}</h2>
              <p>{t("userDashboard.builders.subtitle")}</p>
            </div>
            <button type="button" onClick={() => navigate("/my-plan")}>
              {t("userDashboard.actions.managePlan")}
              <ArrowUpRight size={17} />
            </button>
          </div>

          <div className="user-dashboard-builder-grid">
            {BUILDER_FEATURES.map((feature) => {
              const Icon = feature.icon;
              const isEnabled = enabledBuilderIds.has(feature.id);
              const title = t(`userDashboard.builders.${feature.id}.title`);
              const description = t(
                `userDashboard.builders.${feature.id}.description`
              );

              return (
                <button
                  type="button"
                  className={isEnabled ? "is-enabled" : "is-locked"}
                  key={feature.id}
                  onClick={() => navigate(isEnabled ? feature.path : "/my-plan")}
                >
                  <span className="user-dashboard-builder-icon" aria-hidden="true">
                    <Icon size={20} />
                  </span>
                  <span>
                    <strong>{title}</strong>
                    <small>{description}</small>
                  </span>
                  <em>
                    {isEnabled
                      ? t("userDashboard.builders.enabled")
                      : t("userDashboard.builders.add")}
                  </em>
                </button>
              );
            })}
          </div>
        </article>

        <aside className="user-dashboard-panel user-dashboard-plan-panel">
          <div className="user-dashboard-plan-top">
            <span className="user-dashboard-plan-icon" aria-hidden="true">
              <ShieldCheck size={24} />
            </span>
            <div>
              <span className="user-dashboard-kicker">
                {t("userDashboard.plan.kicker")}
              </span>
              <h2>{planLabel}</h2>
              <p>{statusLabel}</p>
            </div>
          </div>

          <div className="user-dashboard-plan-meter" aria-hidden="true">
            <PieChart size={72} />
            <strong>{Math.round((enabledCount / BUILDER_FEATURES.length) * 100)}%</strong>
          </div>

          <button type="button" onClick={() => navigate("/my-plan")}>
            {t("userDashboard.actions.viewBilling")}
          </button>
        </aside>
      </section>

      <section className="user-dashboard-lower-grid">
        <article className="user-dashboard-panel">
          <div className="user-dashboard-panel-header">
            <div>
              <span className="user-dashboard-kicker">
                {t("userDashboard.usage.kicker")}
              </span>
              <h2>{t("userDashboard.usage.title")}</h2>
              <p>{t("userDashboard.usage.subtitle")}</p>
            </div>
          </div>

          <div className="user-dashboard-usage-list">
            {usageItems.map((item) => {
              const percent = Math.min(100, Math.round((item.value / item.max) * 100));
              const valueLabel = item.suffix
                ? `${item.value}${item.suffix} / ${item.max}${item.suffix}`
                : `${item.value} / ${item.max}`;

              return (
                <div className="user-dashboard-usage-row" key={item.key}>
                  <div>
                    <span>{t(`userDashboard.usage.items.${item.key}`)}</span>
                    <strong>{valueLabel}</strong>
                  </div>
                  <div className="user-dashboard-usage-track">
                    <span style={{ width: `${percent}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </article>

        <article className="user-dashboard-panel">
          <div className="user-dashboard-panel-header">
            <div>
              <span className="user-dashboard-kicker">
                {t("userDashboard.activity.kicker")}
              </span>
              <h2>{t("userDashboard.activity.title")}</h2>
              <p>{t("userDashboard.activity.subtitle")}</p>
            </div>
          </div>

          <div className="user-dashboard-activity-list">
            {recentActivity.map((activity) => {
              const Icon = activity.icon;

              return (
                <div className="user-dashboard-activity-item" key={activity.title}>
                  <span aria-hidden="true">
                    <Icon size={18} />
                  </span>
                  <div>
                    <strong>{activity.title}</strong>
                    <small>{activity.detail}</small>
                  </div>
                </div>
              );
            })}
          </div>
        </article>

        <article className="user-dashboard-panel user-dashboard-next-panel">
          <span className="user-dashboard-plan-icon" aria-hidden="true">
            <Sparkles size={24} />
          </span>
          <h2>{t("userDashboard.next.title")}</h2>
          <p>{t("userDashboard.next.subtitle")}</p>
          <button type="button" onClick={() => navigate("/page-builder")}>
            {t("userDashboard.actions.continueSetup")}
            <ArrowUpRight size={17} />
          </button>
        </article>
      </section>
    </section>
  );
}
