import { useEffect, useMemo, useState } from "react";
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
  TrendingUp,
} from "lucide-react";
import { STORAGE_KEY } from "../PageBuilder/core/PageBuilder.constants";
import { listBuilderProjects } from "../PageBuilder/services/PageBuilder.api";

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

const PLAN_LIMITS = {
  basic: { projects: 1, users: 2, responses: 100, storage: 1 },
  starter: { projects: 3, users: 5, responses: 500, storage: 3 },
  premium: { projects: 8, users: 15, responses: 2500, storage: 10 },
  pro: { projects: 20, users: 50, responses: 10000, storage: 25 },
  full_platform: { projects: 20, users: 50, responses: 10000, storage: 25 },
};

const DEFAULT_DASHBOARD_STATS = {
  projects: 0,
  forms: 0,
  fields: 0,
  responses: 0,
  users: 1,
  storage: 0.2,
  latestFormTitle: "",
  latestResponseDate: "",
  topStatus: "New",
  topStatusCount: 0,
  topValueLabel: "",
  topValue: "",
};

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

function parseProjectSchema(record) {
  const source = record?.draft_schema || record?.draftSchema || record?.schema || record;

  if (typeof source === "string") {
    try {
      return JSON.parse(source);
    } catch {
      return null;
    }
  }

  return source && typeof source === "object" ? source : null;
}

function getLocalProject() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function getResponseDate(response) {
  return response?.createdAt || response?.created_at || response?.submittedAt || response?.submitted_at || "";
}

function getAnswerText(value) {
  if (Array.isArray(value)) return value.map(getAnswerText).filter(Boolean).join(", ");
  if (value && typeof value === "object") return getAnswerText(value.value ?? value.label ?? "");
  return String(value ?? "").trim();
}

function getFormFields(form) {
  if (Array.isArray(form?.fields)) return form.fields;
  if (!Array.isArray(form?.sections)) return [];
  return form.sections.flatMap((section) => section?.fields || []);
}

function buildDashboardStats(projects = []) {
  const statusCounts = new Map();
  const valueCounts = new Map();
  let latestResponse = null;
  let latestFormTitle = "";
  let fields = 0;
  let forms = 0;
  let responses = 0;

  projects.forEach((project) => {
    const projectForms = Array.isArray(project?.forms) ? project.forms : [];
    forms += projectForms.length;

    projectForms.forEach((form) => {
      const formFields = getFormFields(form);
      const formResponses = Array.isArray(form.responses) ? form.responses : [];
      fields += formFields.length;
      responses += formResponses.length;

      formResponses.forEach((response) => {
        const status = response?.status || "New";
        statusCounts.set(status, (statusCounts.get(status) || 0) + 1);

        const responseDate = getResponseDate(response);
        if (responseDate && (!latestResponse || new Date(responseDate) > new Date(getResponseDate(latestResponse)))) {
          latestResponse = response;
          latestFormTitle = form.title || form.name || "";
        }

        Object.entries(response?.answers || {}).forEach(([fieldId, answer]) => {
          const text = getAnswerText(answer);
          if (!text) return;
          const field = formFields.find((item) => item.id === fieldId);
          const label = field?.label || field?.title || fieldId;
          const key = `${label}::${text}`;
          valueCounts.set(key, {
            label,
            value: text,
            count: (valueCounts.get(key)?.count || 0) + 1,
          });
        });
      });
    });
  });

  const [topStatus = "New", topStatusCount = 0] =
    [...statusCounts.entries()].sort((a, b) => b[1] - a[1])[0] || [];
  const topAnswer = [...valueCounts.values()].sort((a, b) => b.count - a.count)[0];

  return {
    ...DEFAULT_DASHBOARD_STATS,
    projects: projects.length,
    forms,
    fields,
    responses,
    users: 1,
    storage: Math.max(0.2, Number((projects.length * 0.2 + responses * 0.002).toFixed(1))),
    latestFormTitle,
    latestResponseDate: latestResponse ? getResponseDate(latestResponse) : "",
    topStatus,
    topStatusCount,
    topValueLabel: topAnswer?.label || "",
    topValue: topAnswer?.value || "",
  };
}

function getPlanLimits(activePlan, subscriptionType) {
  if (subscriptionType === "full_platform") return PLAN_LIMITS.full_platform;
  return PLAN_LIMITS[activePlan] || PLAN_LIMITS.basic;
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
  const [dashboardStats, setDashboardStats] = useState(() =>
    buildDashboardStats([getLocalProject()].filter(Boolean))
  );

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
  const planLimits = getPlanLimits(activePlan, subscriptionType);
  const usageItems = [
    { key: "projects", value: dashboardStats.projects, max: planLimits.projects },
    { key: "users", value: dashboardStats.users, max: planLimits.users },
    { key: "responses", value: dashboardStats.responses, max: planLimits.responses },
    { key: "storage", value: dashboardStats.storage, max: planLimits.storage, suffix: "GB" },
  ];

  useEffect(() => {
    let cancelled = false;

    listBuilderProjects()
      .then((records) => {
        if (cancelled) return;
        const projects = records.map(parseProjectSchema).filter(Boolean);
        const localProject = getLocalProject();
        const allProjects = projects.length ? projects : [localProject].filter(Boolean);
        setDashboardStats(buildDashboardStats(allProjects));
      })
      .catch(() => {
        const localProject = getLocalProject();
        if (!cancelled) setDashboardStats(buildDashboardStats([localProject].filter(Boolean)));
      });

    return () => {
      cancelled = true;
    };
  }, []);

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
      value: dashboardStats.responses.toLocaleString(),
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

  const formDataCards = [
    {
      label: t("userDashboard.formData.totalAnswers", { defaultValue: "Total answers" }),
      value: dashboardStats.responses.toLocaleString(),
      note: t("userDashboard.formData.fromForms", {
        defaultValue: "{{count}} forms, {{fields}} fields",
        count: dashboardStats.forms,
        fields: dashboardStats.fields,
      }),
      icon: ClipboardList,
    },
    {
      label: t("userDashboard.formData.newestAnswer", { defaultValue: "Newest answer" }),
      value: dashboardStats.latestResponseDate
        ? new Date(dashboardStats.latestResponseDate).toLocaleDateString()
        : t("userDashboard.formData.noneYet", { defaultValue: "None yet" }),
      note: dashboardStats.latestFormTitle || t("userDashboard.formData.waiting", { defaultValue: "Waiting for form data" }),
      icon: MessageSquare,
    },
    {
      label: t("userDashboard.formData.topValue", { defaultValue: "Top value" }),
      value: dashboardStats.topValue || dashboardStats.topStatus,
      note: dashboardStats.topValue
        ? dashboardStats.topValueLabel
        : t("userDashboard.formData.topStatus", {
            defaultValue: "{{status}} status, {{count}} answers",
            status: dashboardStats.topStatus,
            count: dashboardStats.topStatusCount,
          }),
      icon: TrendingUp,
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

      <section className="user-dashboard-form-data-grid" aria-label={t("userDashboard.formData.aria", { defaultValue: "Form data summary" })}>
        {formDataCards.map((card) => {
          const Icon = card.icon;

          return (
            <article className="user-dashboard-form-data-card" key={card.label}>
              <span className="user-dashboard-form-data-icon" aria-hidden="true">
                <Icon size={19} />
              </span>
              <div>
                <span>{card.label}</span>
                <strong>{card.value}</strong>
                <small>{card.note}</small>
              </div>
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
