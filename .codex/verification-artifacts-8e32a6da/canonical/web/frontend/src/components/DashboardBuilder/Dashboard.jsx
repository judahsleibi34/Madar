import {
  Activity,
  BarChart3,
  Clock3,
  Database,
  DollarSign,
  FolderKanban,
  HardDrive,
  Server,
  TrendingUp,
  Users,
  Wifi,
} from "lucide-react";
import { getAdminDashboardContent } from "../../content";
import WeeklyScreenTimePanel from "./WeeklyScreenTimePanel";

const cashData = [18000, 24500, 22000, 31000, 38500, 42000, 51000, 62000];
const userSignalData = [
  { key: "activeUsers", value: "1,284", trend: "+8.2%", percent: 82 },
  { key: "sessions", value: "6,420", trend: "+12.4%", percent: 74 },
  { key: "signups", value: "124", trend: "+5.1%", percent: 58 },
  { key: "conversion", value: "6.45%", trend: "+0.8%", percent: 64 },
];

const serviceHealthData = [
  { key: "apiLatency", value: "142ms", percent: 42 },
  { key: "errorRate", value: "0.08%", percent: 8 },
  { key: "queueDepth", value: "24", percent: 24 },
  { key: "databaseLoad", value: "68%", percent: 68 },
];

function OverviewCard({ title, value, sub, icon: Icon, variant }) {
  return (
    <article className={`overview-card ${variant}`} aria-label={`${title}: ${value}`}>
      <div className="overview-card-top">
        <div>
          <p>{title}</p>
          <h2>{value}</h2>
        </div>

        <div className="overview-icon">
          <Icon size={22} />
        </div>
      </div>

      <span className="overview-sub">
        <TrendingUp size={14} />
        {sub}
      </span>
    </article>
  );
}

function MetricRow({ label, value, percent }) {
  return (
    <div className="metric-row">
      <div className="metric-row-header">
        <span>{label}</span>
        <strong>{value}</strong>
      </div>

      <div className="metric-track">
        <div style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

function SignalCard({ label, value, trend, percent }) {
  return (
    <article className="admin-signal-card">
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <em>{trend}</em>
      <div className="admin-signal-track" aria-hidden="true">
        <span style={{ width: `${percent}%` }} />
      </div>
    </article>
  );
}

export default function Dashboard({
  currentUser = null,
  lang = "en",
  themeMode = "light",
  weeklyScreenTimeSeconds = 0,
}) {
  const safeLang = lang === "ar" ? "ar" : "en";
  const t = getAdminDashboardContent(lang);
  const maxCash = Math.max(...cashData);
  const isRtl = safeLang === "ar";

  return (
    <section
      className="dashboard-page admin-dashboard-shell"
      dir={isRtl ? "rtl" : "ltr"}
      data-language={safeLang}
      data-theme={themeMode}
    >
      <header className="admin-dashboard-header app-page-intro">
        <div>
          <h1>{t.title}</h1>
          <p>{t.subtitle}</p>
          <div className="admin-dashboard-header-meta" aria-label={t.platformHealth}>
            <span>
              <Activity size={14} aria-hidden="true" />
              {t.liveStatus}
            </span>
            <span>{t.lastUpdated}</span>
            <span>{t.platformHealth}</span>
            <span>{t.todayOrders}</span>
            <span>{t.todayRevenue}</span>
          </div>
        </div>
      </header>

      <section className="overview-grid" aria-label={t.title}>
        <OverviewCard
          title={t.runningProjects}
          value="18"
          sub={t.projectsSub}
          icon={FolderKanban}
          variant="navy"
        />

        <OverviewCard
          title={t.users}
          value="4,862"
          sub={t.usersSub}
          icon={Users}
          variant="red"
        />

        <OverviewCard
          title={t.totalRevenue}
          value="$62.4K"
          sub={t.revenueSub}
          icon={DollarSign}
          variant="olive"
        />

        <OverviewCard
          title={t.uptime}
          value="99.98%"
          sub={t.uptimeSub}
          icon={Clock3}
          variant="navy"
        />
      </section>

      <WeeklyScreenTimePanel
        currentUser={currentUser}
        currentSeconds={weeklyScreenTimeSeconds}
      />

      <section className="admin-monitor-grid">
        <article className="dashboard-panel admin-user-signals-panel">
          <div className="dashboard-panel-header">
            <div>
              <h2>{t.userSignals}</h2>
              <p>{t.userSignalsSubtitle}</p>
            </div>

            <div className="panel-icon">
              <Users size={22} />
            </div>
          </div>

          <div className="admin-signal-grid">
            {userSignalData.map((item) => (
              <SignalCard
                key={item.key}
                label={t[item.key]}
                value={item.value}
                trend={item.trend}
                percent={item.percent}
              />
            ))}
          </div>
        </article>

        <article className="dashboard-panel admin-service-health-panel">
          <div className="dashboard-panel-header">
            <div>
              <h2>{t.serviceHealth}</h2>
              <p>{t.serviceHealthSubtitle}</p>
            </div>

            <div className="panel-icon">
              <Server size={22} />
            </div>
          </div>

          <div className="metrics-list">
            {serviceHealthData.map((item) => (
              <MetricRow
                key={item.key}
                label={t[item.key]}
                value={item.value}
                percent={item.percent}
              />
            ))}
          </div>
        </article>
      </section>

      <section className="admin-dashboard-grid">
        <article className="dashboard-panel cash-panel">
          <div className="dashboard-panel-header">
            <div>
              <h2>{t.cashFlow}</h2>
              <p>{t.cashSubtitle}</p>
            </div>

            <div className="panel-icon">
              <BarChart3 size={22} />
            </div>
          </div>

          <div className="dashboard-panel-meta">
            <span>{t.chartScope}</span>
            <strong>+$44K</strong>
          </div>

          <div className="cash-chart" dir="ltr" aria-label={t.cashFlow}>
            {cashData.map((value, index) => (
              <div className="cash-bar-item" key={`${t.months[index]}-${value}`}>
                <div
                  className="cash-bar"
                  style={{ height: `${(value / maxCash) * 100}%` }}
                >
                  <span>${Math.round(value / 1000)}K</span>
                </div>

                <small dir={isRtl ? "rtl" : "ltr"}>{t.months[index]}</small>
              </div>
            ))}
          </div>
        </article>

        <article className="dashboard-panel server-panel">
          <div className="dashboard-panel-header">
            <div>
              <h2>{t.serverInfo}</h2>
              <p>{t.serverSubtitle}</p>
            </div>

            <div className="panel-icon">
              <Server size={22} />
            </div>
          </div>

          <div className="server-info-list">
            <div>
              <span>
                <Wifi size={17} />
                {t.serverStatus}
              </span>

              <strong className="server-status-healthy">{t.healthy}</strong>
            </div>

            <div>
              <span>
                <Database size={17} />
                {t.activeServices}
              </span>

              <strong>4</strong>
            </div>

            <div>
              <span>
                <Activity size={17} />
                {t.serverRegion}
              </span>

              <strong>{t.regionValue}</strong>
            </div>
          </div>
        </article>
      </section>

      <section className="admin-dashboard-grid lower">
        <article className="dashboard-panel usage-panel">
          <div className="dashboard-panel-header">
            <div>
              <h2>{t.usage}</h2>
              <p>{t.usageSubtitle}</p>
            </div>

            <div className="panel-icon">
              <HardDrive size={22} />
            </div>
          </div>

          <div className="metrics-list">
            <MetricRow label={t.cpu} value="42%" percent={42} />
            <MetricRow label={t.memory} value="68%" percent={68} />
            <MetricRow label={t.storage} value="74%" percent={74} />
            <MetricRow label={t.network} value="36%" percent={36} />
          </div>
        </article>

        <article className="dashboard-panel uptime-panel">
          <div className="uptime-circle">
            <div>
              <strong>99.98%</strong>
              <span>{t.uptime}</span>
            </div>
          </div>

          <h2>{t.uptime}</h2>
          <p>{t.uptimeSub}</p>
        </article>
      </section>
    </section>
  );
}


