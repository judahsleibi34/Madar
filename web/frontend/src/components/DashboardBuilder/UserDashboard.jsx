import { useWorkspaceCapabilities } from "../../commercial/capabilityContext";
import { useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import {
  BellRing,
  CalendarClock,
  CircleCheckBig,
  CreditCard,
  ExternalLink,
  FileText,
  HardDrive,
  KeyRound,
  ListRestart,
  Users,
} from "lucide-react";
import { getLocalTenantPath } from "../PageBuilder/core/PageBuilder.routing";
import { getBuilderWorkspacePath } from "../PageBuilder/core/PageBuilder.workspaceRouting";
import WeeklyScreenTimePanel from "./WeeklyScreenTimePanel";
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
  usedBytes: 0,
  quotaBytes: 0,
  permittedUsers: 0,
  permissionTypes: [],
  projectId: "",
  websitePath: "",
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
  const { ready, can } = useWorkspaceCapabilities();
  const mayBuild = can("forms") || can("page_builder");
  const mayReserve = can("reservation_management");
  const mayWebsite = can("page_builder");
  const initialMetrics = readDashboardMetricsCache(cacheScope);
  const [metrics, setMetrics] = useState(() => initialMetrics || EMPTY_METRICS);
  const [loading, setLoading] = useState(() => !initialMetrics);

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
      if (!ready || !mayBuild) return;
      const cachedMetrics = readDashboardMetricsCache(cacheScope);
      if (cachedMetrics) {
        setMetrics(cachedMetrics);
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
      const projects = remoteProjects;
      const primaryProject = projects[0] || null;
      const primaryRecord = records[0] || null;
      const projectId = String(
        primaryRecord?.id || primaryRecord?.project_id || primaryProject?.id || ""
      );

      const [storage, reservations, memberGroups] = await Promise.all([
        fetchBuilderStorageUsage().catch(() => null),
        mayReserve ? loadAllReservations().catch(() => []) : Promise.resolve([]),
        Promise.all(
          (mayWebsite ? records : []).map((record) => {
            const projectId = record?.id || record?.project_id;
            return projectId
              ? fetchBuilderSiteMembers(projectId).catch(() => [])
              : Promise.resolve([]);
          })
        ),
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
        usedBytes,
        quotaBytes: Number(storage?.quota_bytes || 0),
        permittedUsers: uniqueMembers.size,
        permissionTypes: getPermissionTypes(projects),
        projectId,
        websitePath: primaryProject ? getLocalTenantPath(primaryProject) : "",
      };
      writeDashboardMetricsCache(cacheScope, nextMetrics);
      setMetrics(nextMetrics);
      setLoading(false);
    };

    loadMetrics();
    return () => {
      cancelled = true;
    };
  }, [cacheScope, ready, mayBuild, mayReserve, mayWebsite]);

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
      {
        id: "reservation-notifications",
        label: "Reservation notifications",
        value: metrics.newReservations.toLocaleString(),
        note: reservationNote,
        icon: BellRing,
        accent: metrics.newReservations > 0,
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
        id: "plan",
        label: "Plan",
        value: planLabel,
        note: planStatus,
        icon: CreditCard,
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
        note: permissionNote,
        icon: KeyRound,
      },
    ];
  }, [metrics, planLabel, planStatus]);

  const responsesPath = metrics.projectId
    ? getBuilderWorkspacePath(metrics.projectId, "responses", "builder-responses")
    : "/builder-responses";
  const websitePath = metrics.websitePath || (
    metrics.projectId
      ? getBuilderWorkspacePath(metrics.projectId, "publish")
      : "/page-builder"
  );

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

      <nav className="user-dashboard-quick-actions" aria-label="Form and website shortcuts">
        <Link to={responsesPath + "/incomplete"}>
          <ListRestart size={18} aria-hidden="true" />
          <span>Incomplete forms</span>
        </Link>
        <Link to={responsesPath + "/completed"}>
          <CircleCheckBig size={18} aria-hidden="true" />
          <span>Completed forms</span>
        </Link>
        {mayWebsite && <Link className="is-primary" to={websitePath}>
          <ExternalLink size={18} aria-hidden="true" />
          <span>View website</span>
        </Link>}
      </nav>

      <section
        className="user-dashboard-metrics-grid"
        aria-label="Workspace metrics"
        aria-busy={loading}
      >
        {cards.filter((card) => !card.id.startsWith("reservation-") || mayReserve).filter((card) => !["permitted-users", "permission-types"].includes(card.id) || mayWebsite).map((card) => {
          const Icon = card.icon;
          return (
            <article
              className={
                "user-dashboard-metric-card" +
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
  const { revision } = useWorkspaceCapabilities();
  const cacheScope = `${getDashboardCacheScope(props.user)}:${revision}`;
  return (
    <UserDashboardContent
      key={cacheScope || "uncached"}
      {...props}
      cacheScope={cacheScope}
    />
  );
}
