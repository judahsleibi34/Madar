import { useLayoutEffect, useState } from "react";

import {
  Activity,
  BarChart3,
  Clock3,
  Database,
  DollarSign,
  FolderKanban,
  HardDrive,
  Menu,
  Server,
  TrendingUp,
  Users,
  Wifi,
  X,
} from "lucide-react";

import DashboardSidebar from "./DashboardSidebar";

const dashboardText = {
  en: {
    title: "Dashboard",
    subtitle:
      "Monitor platform activity, active projects, revenue, system health, and resource usage.",

    runningProjects: "Running Projects",
    users: "Users",
    totalRevenue: "Total Revenue",
    uptime: "Uptime",

    projectsSub: "+8 this month",
    usersSub: "+124 new users",
    revenueSub: "+18.4% growth",
    uptimeSub: "Last 30 days",

    serverInfo: "Server Info",
    serverSubtitle: "Core platform services status",
    serverStatus: "Status",
    healthy: "Healthy",
    activeServices: "Active Services",
    serverRegion: "Region",
    regionValue: "Middle East",

    usage: "Usage",
    usageSubtitle: "Current infrastructure usage",
    cpu: "CPU",
    memory: "Memory",
    storage: "Storage",
    network: "Network",

    cashFlow: "Cash Through Time",
    cashSubtitle: "Monthly revenue performance",

    months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"],

    openMenu: "Open dashboard menu",
    closeMenu: "Close dashboard menu",
  },

  ar: {
    title: "لوحة التحكم",
    subtitle:
      "راقب نشاط المنصة والمشاريع النشطة والإيرادات وصحة النظام واستخدام الموارد.",

    runningProjects: "المشاريع النشطة",
    users: "المستخدمون",
    totalRevenue: "إجمالي الإيرادات",
    uptime: "وقت التشغيل",

    projectsSub: "+8 هذا الشهر",
    usersSub: "+124 مستخدمًا جديدًا",
    revenueSub: "+18.4% نمو",
    uptimeSub: "آخر 30 يومًا",

    serverInfo: "معلومات الخادم",
    serverSubtitle: "حالة خدمات المنصة الأساسية",
    serverStatus: "الحالة",
    healthy: "مستقر",
    activeServices: "الخدمات النشطة",
    serverRegion: "المنطقة",
    regionValue: "الشرق الأوسط",

    usage: "الاستخدام",
    usageSubtitle: "الاستخدام الحالي للبنية التحتية",
    cpu: "المعالج",
    memory: "الذاكرة",
    storage: "التخزين",
    network: "الشبكة",

    cashFlow: "التدفق المالي عبر الزمن",
    cashSubtitle: "أداء الإيرادات الشهرية",

    months: ["ينا", "فبر", "مار", "أبر", "ماي", "يون", "يول", "أغس"],

    openMenu: "فتح قائمة لوحة التحكم",
    closeMenu: "إغلاق قائمة لوحة التحكم",
  },
};

const cashData = [18000, 24500, 22000, 31000, 38500, 42000, 51000, 62000];

function forceScrollTop() {
  if ("scrollRestoration" in window.history) {
    window.history.scrollRestoration = "manual";
  }

  window.scrollTo({
    top: 0,
    behavior: "instant",
  });

  document.documentElement.scrollTop = 0;
  document.body.scrollTop = 0;

  const root = document.getElementById("root");
  if (root) {
    root.scrollTop = 0;
  }

  const dashboardPage = document.querySelector(".admin-dashboard-page");
  if (dashboardPage) {
    dashboardPage.scrollTop = 0;
  }

  const dashboardLayout = document.querySelector(".admin-dashboard-layout");
  if (dashboardLayout) {
    dashboardLayout.scrollTop = 0;
  }
}

function OverviewCard({ title, value, sub, icon: Icon, variant }) {
  return (
    <article className={`overview-card ${variant}`}>
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

export default function Dashboard({
  lang = "en",
  onLogout,
  user,
  onLanguageChange,
  themeMode = "light",
  onThemeModeChange,
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useLayoutEffect(() => {
    forceScrollTop();

    const frame1 = requestAnimationFrame(() => {
      forceScrollTop();
    });

    const frame2 = requestAnimationFrame(() => {
      forceScrollTop();
    });

    const timeout1 = setTimeout(() => {
      forceScrollTop();
    }, 0);

    const timeout2 = setTimeout(() => {
      forceScrollTop();
    }, 100);

    return () => {
      cancelAnimationFrame(frame1);
      cancelAnimationFrame(frame2);
      clearTimeout(timeout1);
      clearTimeout(timeout2);
    };
  }, []);

  const t = dashboardText[lang] || dashboardText.en;
  const maxCash = Math.max(...cashData);
  const isRtl = lang === "ar";

  const closeSidebar = () => {
    setSidebarOpen(false);
  };

  const handleLogout = () => {
    closeSidebar();
    onLogout?.();
  };

  return (
    <div
      className={`admin-dashboard-layout ${isRtl ? "is-rtl" : "is-ltr"}${
        sidebarOpen ? " sidebar-open" : ""
      }`}
      dir="ltr"
    >
      <button
        type="button"
        className="dashboard-mobile-menu-button"
        onClick={() => setSidebarOpen((open) => !open)}
        aria-label={sidebarOpen ? t.closeMenu : t.openMenu}
        aria-expanded={sidebarOpen}
        aria-controls="dashboard-sidebar"
      >
        {sidebarOpen ? <X size={22} /> : <Menu size={22} />}
      </button>

      <button
        type="button"
        className="dashboard-sidebar-backdrop"
        onClick={closeSidebar}
        aria-label={t.closeMenu}
      />

      <DashboardSidebar
        id="dashboard-sidebar"
        lang={lang}
        user={user}
        onLogout={handleLogout}
        onLanguageChange={onLanguageChange}
        onNavigate={closeSidebar}
        themeMode={themeMode}
        onThemeModeChange={onThemeModeChange}
      />

      <main className="admin-dashboard-page" dir={isRtl ? "rtl" : "ltr"}>
        <div className="admin-dashboard-shell">
          <header className="admin-dashboard-header">
            <div>
              <h1>{t.title}</h1>
              <p>{t.subtitle}</p>
            </div>
          </header>

          <section className="overview-grid">
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

              <div className="cash-chart">
                {cashData.map((value, index) => (
                  <div
                    className="cash-bar-item"
                    key={`${t.months[index]}-${value}`}
                  >
                    <div
                      className="cash-bar"
                      style={{ height: `${(value / maxCash) * 100}%` }}
                    >
                      <span>${Math.round(value / 1000)}K</span>
                    </div>

                    <small>{t.months[index]}</small>
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

                  <strong>{t.healthy}</strong>
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
        </div>
      </main>
    </div>
  );
}