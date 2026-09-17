import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  BellRing,
  CalendarClock,
  CircleCheckBig,
  CreditCard,
  ExternalLink,
  FileText,
  Globe2,
  HardDrive,
  KeyRound,
  ListRestart,
  ShoppingBag,
  SlidersHorizontal,
  Users,
} from "lucide-react";
import { STORAGE_KEY } from "../PageBuilder/core/PageBuilder.constants";
import { getProductionTenantUrl } from "../PageBuilder/core/PageBuilder.routing";
import { getBuilderWorkspacePath } from "../PageBuilder/core/PageBuilder.workspaceRouting";
import WeeklyScreenTimePanel from "./WeeklyScreenTimePanel";
import { fetchSiteVisitMetrics } from "../../services/siteVisitApi";
import {
  getDashboardCacheScope,
  readDashboardMetricsCache,
  writeDashboardMetricsCache,
} from "./utils/dashboardSnapshotCache";
import {
  fetchBuilderSiteMembers,
  fetchBuilderStorageUsage,
  listBuilderProjects,
  listBuilderReservations,
} from "../PageBuilder/services/PageBuilder.api";

const PERMISSION_LABELS = {
  viewProtectedPages: "Protected pages",
  submitForms: "Form submissions",
  makeReservations: "Reservations",
};

const EMPTY_METRICS = {
  projects: 0,
  forms: 0,
  reservationForms: 0,
  newReservations: 0,
  totalReservations: 0,
  websiteVisits: 0,
  storeVisits: 0,
  usedBytes: 0,
  quotaBytes: 0,
  permittedUsers: 0,
  permissionTypes: [],
  projectId: "",
  storeUrl: "",
  websiteUrl: "",
};

const DASHBOARD_VISIBILITY_STORAGE_KEY = "madar-dashboard-card-visibility-v1";

const readHiddenDashboardCards = (scope) => {
  try {
    const value = JSON.parse(
      window.localStorage.getItem(
        `${DASHBOARD_VISIBILITY_STORAGE_KEY}:${scope}`,
      ) || "[]",
    );
    return Array.isArray(value) ? value.map(String) : [];
  } catch {
    return [];
  }
};

const normalizeDashboardMetrics = (value) => {
  const cached = value && typeof value === "object" ? value : {};
  return {
    ...EMPTY_METRICS,
    ...cached,
    permissionTypes: Array.isArray(cached.permissionTypes)
      ? cached.permissionTypes
      : EMPTY_METRICS.permissionTypes,
  };
};

function toTitleCase(value) {
  return String(value || "").replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatPlanLabel(plan, subscriptionType, builderType, t) {
  if (plan) {
    return t("userDashboard.plans." + plan, { defaultValue: toTitleCase(plan) });
  }
  if (subscriptionType === "full_platform") {
    return t("userDashboard.plans.fullPlatform", { defaultValue: "Full platform" });
  }
  if (builderType) {
    return t("userDashboard.plans.builder", {
      builder: toTitleCase(builderType),
      defaultValue: toTitleCase(builderType) + " plan",
    });
  }
  return t("userDashboard.plans.workspace", { defaultValue: "Workspace plan" });
}

function formatStatus(status, t) {
  if (!status) return t("userDashboard.status.pending", { defaultValue: "Pending" });
  return t("userDashboard.status." + status, { defaultValue: toTitleCase(status) });
}

function parseProjectSchema(record) {
  const source = record?.draft_schema || record?.draftSchema || record?.schema || record;
  if (!source) return null;
  if (typeof source === "string") {
    try {
      return JSON.parse(source);
    } catch {
      return null;
    }
  }
  return typeof source === "object" ? source : null;
}

function getLocalProject() {
  try {
    return parseProjectSchema(JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"));
  } catch {
    return null;
  }
}

function countReservationForms(project) {
  let count = 0;
  const inspect = (element) => {
    if (element?.type !== "reservationBlock") return;
    const sourceId = element.connectedReservationBlockId;
    if (!sourceId || sourceId === element.id) count += 1;
  };

  (project?.pages || []).forEach((page) => {
    (page?.sections || []).forEach((section) => {
      (section?.freeElements || []).forEach(inspect);
      (section?.rows || []).forEach((row) => {
        (row?.columns || []).forEach((column) => {
          (column?.elements || []).forEach(inspect);
        });
      });
    });
  });

  return count;
}

function getPermissionTypes(projects) {
  const enabled = new Set();
  projects.forEach((project) => {
    (project?.roles || []).forEach((role) => {
      Object.entries(role?.permissions || {}).forEach(([permission, isEnabled]) => {
        if (isEnabled) enabled.add(permission);
      });
    });
  });
  return Array.from(enabled).map(
    (permission) => PERMISSION_LABELS[permission] || toTitleCase(permission)
  );
}

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return bytes + " B";
  const units = ["KB", "MB", "GB", "TB"];
  let amount = bytes / 1024;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  const precision = amount >= 10 ? 0 : 1;
  return amount.toFixed(precision) + " " + units[index];
}

async function loadAllReservations() {
  const reservations = [];
  let offset = 0;

  for (let page = 0; page < 10; page += 1) {
    const result = await listBuilderReservations({ limit: 100, offset });
    reservations.push(...result.reservations);
    if (!result.pagination.has_more || result.reservations.length === 0) break;
    offset += result.reservations.length;
  }

  return reservations;
}

function UserDashboardContent({ user, weeklyScreenTimeSeconds = 0, cacheScope = "" }) {
  const { t } = useTranslation();
  const visibilityScope = cacheScope || `user:${user?.id || user?.email || "default"}`;
  const customizerRef = useRef(null);
  const [customizerOpen, setCustomizerOpen] = useState(false);
  const [hiddenCardIds, setHiddenCardIds] = useState(() =>
    readHiddenDashboardCards(visibilityScope),
  );
  const cachedInitialMetrics = readDashboardMetricsCache(cacheScope);
  const initialMetrics = cachedInitialMetrics
    ? normalizeDashboardMetrics(cachedInitialMetrics)
    : null;
  const [metrics, setMetrics] = useState(() => initialMetrics || EMPTY_METRICS);
  const [loading, setLoading] = useState(() => !initialMetrics);

  useEffect(() => {
    try {
      window.localStorage.setItem(
        `${DASHBOARD_VISIBILITY_STORAGE_KEY}:${visibilityScope}`,
        JSON.stringify(hiddenCardIds),
      );
    } catch {
      // Keep the current selection for this session if storage is unavailable.
    }
  }, [hiddenCardIds, visibilityScope]);

  useEffect(() => {
    if (!customizerOpen) return undefined;
    const closeOnOutsidePress = (event) => {
      if (!customizerRef.current?.contains(event.target)) {
        setCustomizerOpen(false);
      }
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") setCustomizerOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsidePress);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePress);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [customizerOpen]);

  const displayName =
    user?.first_name ||
    user?.name?.split?.(" ")?.[0] ||
    user?.email?.split?.("@")?.[0] ||
    t("userDashboard.fallbackName", { defaultValue: "there" });

  const planLabel = formatPlanLabel(
    user?.plan,
    user?.subscription_type,
    user?.builder_type,
    t
  );
  const planStatus = formatStatus(user?.payment_status, t);

  useEffect(() => {
    let cancelled = false;

    const loadMetrics = async () => {
      const cachedMetrics = readDashboardMetricsCache(cacheScope);
      if (cachedMetrics) {
        setMetrics(normalizeDashboardMetrics(cachedMetrics));
        setLoading(false);
      }

      let records;
      try {
        const result = await listBuilderProjects({ limit: 100 });
        records = result.projects;
      } catch {
        if (cachedMetrics) return;
        records = [];
      }

      const remoteProjects = records.map(parseProjectSchema).filter(Boolean);
      const localProject = getLocalProject();
      const projects =
        remoteProjects.length > 0
          ? remoteProjects
          : localProject
            ? [localProject]
            : [];
      const primaryProject = projects[0] || null;
      const primaryRecord = records[0] || null;
      const projectId = String(
        primaryRecord?.id || primaryRecord?.project_id || primaryProject?.id || ""
      );

      const [storage, reservations, memberGroups, visitMetrics] = await Promise.all([
        fetchBuilderStorageUsage().catch(() => null),
        loadAllReservations().catch(() => []),
        Promise.all(
          records.map((record) => {
            const projectId = record?.id || record?.project_id;
            return projectId
              ? fetchBuilderSiteMembers(projectId).catch(() => [])
              : Promise.resolve([]);
          })
        ),
        fetchSiteVisitMetrics().catch(() => ({
          website_visits: 0,
          store_visits: 0,
        })),
      ]);

      if (cancelled) return;

      const uniqueMembers = new Map();
      memberGroups.flat().forEach((member) => {
        if (String(member?.status || "Active").toLowerCase() === "disabled") return;
        const key = member?.userId || member?.user_id || member?.email || member?.id;
        if (key) uniqueMembers.set(String(key), member);
      });

      const usedBytes =
        Number(storage?.used_bytes || 0) + Number(storage?.reserved_bytes || 0);

      const nextMetrics = {
        projects: projects.length,
        forms: projects.reduce(
          (total, project) => total + (Array.isArray(project?.forms) ? project.forms.length : 0),
          0
        ),
        reservationForms: projects.reduce(
          (total, project) => total + countReservationForms(project),
          0
        ),
        newReservations: reservations.filter(
          (reservation) => String(reservation?.status || "new").toLowerCase() === "new"
        ).length,
        totalReservations: reservations.length,
        websiteVisits: Number(visitMetrics?.website_visits || 0),
        storeVisits: Number(visitMetrics?.store_visits || 0),
        usedBytes,
        quotaBytes: Number(storage?.quota_bytes || 0),
        permittedUsers: uniqueMembers.size,
        permissionTypes: getPermissionTypes(projects),
        projectId,
        storeUrl: primaryProject ? getProductionTenantUrl(primaryProject, "/shop") : "",
        websiteUrl: primaryProject ? getProductionTenantUrl(primaryProject) : "",
      };
      writeDashboardMetricsCache(cacheScope, nextMetrics);
      setMetrics(nextMetrics);
      setLoading(false);
    };

    loadMetrics();
    return () => {
      cancelled = true;
    };
  }, [cacheScope]);

  const cards = useMemo(() => {
    const projectNote =
      metrics.projects === 1
        ? "Across 1 website project"
        : "Across " + metrics.projects + " website projects";
    const reservationNote =
      metrics.totalReservations === 1
        ? "1 total reservation"
        : metrics.totalReservations + " total reservations";
    const permissionNote =
      metrics.permissionTypes.length > 0
        ? metrics.permissionTypes.join(" · ")
        : "No permission types enabled";
    const storagePercent =
      metrics.quotaBytes > 0
        ? Math.min(100, Math.round((metrics.usedBytes / metrics.quotaBytes) * 100))
        : 0;

    return [
      {
        id: "plan",
        label: "Plan",
        value: planLabel,
        note: planStatus,
        icon: CreditCard,
      },
      {
        id: "website-visits",
        label: "Website visits",
        value: metrics.websiteVisits.toLocaleString(),
        note: "Every published website opening",
        icon: Globe2,
      },
      {
        id: "store-visits",
        label: "Store visits",
        value: metrics.storeVisits.toLocaleString(),
        note: "Every published store opening",
        icon: ShoppingBag,
      },
      {
        id: "reservation-notifications",
        label: "Reservation notifications",
        value: metrics.newReservations.toLocaleString(),
        note: reservationNote,
        icon: BellRing,
        accent: metrics.newReservations > 0,
      },
      {
        id: "permitted-users",
        label: "Users with permissions",
        value: metrics.permittedUsers.toLocaleString(),
        note: "Active assigned members",
        icon: Users,
      },
      {
        id: "permission-types",
        label: "Permission types",
        value:
          metrics.permissionTypes.length +
          (metrics.permissionTypes.length === 1 ? " type" : " types"),
        note:
          metrics.permissionTypes.length > 0
            ? "Enabled workspace permissions"
            : permissionNote,
        icon: KeyRound,
      },
      {
        id: "storage",
        label: "Used space",
        value: formatBytes(metrics.usedBytes),
        note:
          metrics.quotaBytes > 0
            ? storagePercent + "% of " + formatBytes(metrics.quotaBytes)
            : "Storage usage",
        icon: HardDrive,
        progress: storagePercent,
      },
      {
        id: "forms",
        label: "Forms used",
        value: metrics.forms.toLocaleString(),
        note: projectNote,
        icon: FileText,
      },
      {
        id: "reservation-forms",
        label: "Reservation forms used",
        value: metrics.reservationForms.toLocaleString(),
        note: "Configured booking blocks",
        icon: CalendarClock,
      },
    ];
  }, [metrics, planLabel, planStatus]);

  const responsesPath = metrics.projectId
    ? getBuilderWorkspacePath(metrics.projectId, "responses", "builder-responses")
    : "/builder-responses";
  const visibleCards = cards.filter((card) => !hiddenCardIds.includes(card.id));

  const toggleCardVisibility = (cardId) => {
    setHiddenCardIds((current) =>
      current.includes(cardId)
        ? current.filter((id) => id !== cardId)
        : [...current, cardId],
    );
  };

  return (
    <div className="user-dashboard-page">
      <header className="user-dashboard-hero app-page-intro">
        <h1>
          {t("userDashboard.welcome", {
            name: displayName,
            defaultValue: "Welcome, " + displayName,
          })}
        </h1>
        <p>
          {t("userDashboard.metricsSubtitle", {
            defaultValue:
              "A clear view of your forms, reservations, storage, plan, and access.",
          })}
        </p>
      </header>

      <nav className="user-dashboard-quick-actions" aria-label="Form, website, and store shortcuts">
        <Link to={responsesPath + "/incomplete"}>
          <ListRestart size={18} aria-hidden="true" />
          <span>Incomplete forms</span>
        </Link>
        <Link to={responsesPath + "/completed"}>
          <CircleCheckBig size={18} aria-hidden="true" />
          <span>Completed forms</span>
        </Link>
        {metrics.websiteUrl && (
          <a
            className="is-primary"
            href={metrics.websiteUrl}
            target="_blank"
            rel="noreferrer"
          >
            <ExternalLink size={18} aria-hidden="true" />
            <span>View website</span>
          </a>
        )}
        {metrics.storeUrl && (
          <a
            className="is-primary"
            href={metrics.storeUrl}
            target="_blank"
            rel="noreferrer"
          >
            <ShoppingBag size={18} aria-hidden="true" />
            <span>View store</span>
          </a>
        )}
        <div className="user-dashboard-customizer" ref={customizerRef}>
          <button
            type="button"
            className="user-dashboard-customizer-toggle"
            aria-expanded={customizerOpen}
            aria-controls="dashboard-card-checklist"
            onClick={() => setCustomizerOpen((current) => !current)}
          >
            <SlidersHorizontal size={18} aria-hidden="true" />
            <span>Customize dashboard</span>
          </button>
          {customizerOpen && (
            <div
              className="user-dashboard-customizer-menu"
              id="dashboard-card-checklist"
            >
              <div className="user-dashboard-customizer-header">
                <div>
                  <strong>Dashboard cards</strong>
                  <span>Choose what you want to see</span>
                </div>
                <button
                  type="button"
                  className="user-dashboard-customizer-reset"
                  onClick={() => setHiddenCardIds([])}
                  disabled={hiddenCardIds.length === 0}
                >
                  Show all
                </button>
              </div>
              <div className="user-dashboard-customizer-list">
                {cards.map((card) => (
                  <label key={card.id}>
                    <input
                      type="checkbox"
                      checked={!hiddenCardIds.includes(card.id)}
                      onChange={() => toggleCardVisibility(card.id)}
                    />
                    <span>{card.label}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
      </nav>

      <section
        className="user-dashboard-metrics-grid"
        aria-label="Workspace metrics"
        aria-busy={loading}
      >
        {visibleCards.map((card) => {
          const Icon = card.icon;
          return (
            <article
              className={
                "user-dashboard-metric-card" +
                (card.id === "plan" ? " user-dashboard-metric-card--plan" : "") +
                (card.accent ? " user-dashboard-metric-card--accent" : "")
              }
              key={card.id}
            >
              <div className="user-dashboard-metric-heading">
                <span className="user-dashboard-metric-icon" aria-hidden="true">
                  <Icon size={21} />
                </span>
                <span className="user-dashboard-metric-label">{card.label}</span>
              </div>
              <div>
                <strong className="user-dashboard-metric-value">
                  {loading ? "—" : card.value}
                </strong>
                <p className="user-dashboard-metric-note">
                  {loading ? "Loading workspace data…" : card.note}
                </p>
                {typeof card.progress === "number" && (
                  <div
                    className="user-dashboard-storage-track"
                    role="progressbar"
                    aria-label="Storage used"
                    aria-valuemin="0"
                    aria-valuemax="100"
                    aria-valuenow={card.progress}
                  >
                    <span style={{ width: card.progress + "%" }} />
                  </div>
                )}
              </div>
            </article>
          );
        })}
        {visibleCards.length === 0 && (
          <div className="user-dashboard-metrics-empty">
            No cards selected. Use Customize dashboard to add cards.
          </div>
        )}
      </section>

      <WeeklyScreenTimePanel
        currentUser={user}
        currentSeconds={weeklyScreenTimeSeconds}
        projectId={metrics.projectId}
      />
    </div>
  );
}

export default function UserDashboard(props) {
  const cacheScope = getDashboardCacheScope(props.user);
  return (
    <UserDashboardContent
      key={cacheScope || "uncached"}
      {...props}
      cacheScope={cacheScope}
    />
  );
}
