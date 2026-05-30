import {
  Home,
  LayoutDashboard,
  PanelsTopLeft,
  Settings,
  LogOut,
  Grid2X2,
  Languages,
  Database,
  ClipboardList,
  CreditCard,
} from "lucide-react";
import { useLocation } from "react-router-dom";
import SmartLink from "../SmartLink";
import { resolveMediaUrl } from "../../utils/media";

const sidebarText = {
  en: {
    title: "Dashboard",
    subtitle: "Madar",
    home: "Home",
    dashboard: "Dashboard",
    pageBuilder: "Page Builder",
    responses: "Submissions",
    data: "Data Logs",
    settings: "Settings",
    logout: "Logout",
    fallbackName: "User",
    switchLang: "AR",
    plan: "My Plan",
  },
  ar: {
    responses: "الردود",
    data: "البيانات",
    title: "لوحة التحكم",
    subtitle: "مدار",
    home: "الرئيسية",
    dashboard: "لوحة التحكم",
    pageBuilder: "منشئ الصفحات",
    settings: "الإعدادات",
    logout: "تسجيل الخروج",
    fallbackName: "مستخدم",
    switchLang: "EN",
    plan: "خطتي",
  },
};

export default function DashboardSidebar({
  id,
  lang = "en",
  user,
  onLogout,
  onLanguageChange,
  onNavigate,
  hideLanguage = false,
}) {
  const location = useLocation();

  const t = sidebarText[lang] || sidebarText.en;

  const displayName = user?.name || t.fallbackName;
  const displayEmail = user?.email || "";
  const avatarUrl = resolveMediaUrl(user?.avatar || "");
  const avatarLetter = displayName.trim().charAt(0).toUpperCase() || "U";

  const isActive = (path) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  const handleLangToggle = () => {
    onLanguageChange?.(lang === "en" ? "ar" : "en");
  };

  const navItems = [
    {
      path: "/",
      label: t.home,
      icon: <Home size={18} />,
    },
    {
      path: "/dashboard",
      label: t.dashboard,
      icon: <LayoutDashboard size={18} />,
    },
    {
      path: "/page-builder",
      label: t.pageBuilder,
      icon: <PanelsTopLeft size={18} />,
    },
    {
      path: "/builder-responses",
      label: t.responses || "Responses",
      icon: <ClipboardList size={18} />,
    },
    {
      path: "/builder-data",
      label: t.data || "Data",
      icon: <Database size={18} />,
    },
    {
      path: "/my-plan",
      label: t.plan,
      icon: <CreditCard size={18} />,
    },
    {
      path: "/settings",
      label: t.settings,
      icon: <Settings size={18} />,
    },
  ];

  return (
    <aside id={id} className="admin-sidebar">
      <div className="admin-sidebar-top">
        <div className="admin-sidebar-brand">
          <div className="admin-sidebar-icon">
            <Grid2X2 size={22} />
          </div>

          <div>
            <strong>{t.title}</strong>
            <span>{t.subtitle}</span>
          </div>
        </div>

        <nav className="admin-sidebar-nav" aria-label="Dashboard navigation">
          {navItems.map((item) => (
            <SmartLink
              key={item.path}
              to={item.path}
              className={isActive(item.path) ? "active" : ""}
              onClick={onNavigate}
            >
              {item.icon}
              <span>{item.label}</span>
            </SmartLink>
          ))}
        </nav>
      </div>

      <div className="admin-sidebar-bottom">
        {!hideLanguage && (
          <button
            type="button"
            className="admin-sidebar-lang"
            onClick={handleLangToggle}
          >
            <Languages size={18} />
            <span>{t.switchLang}</span>
          </button>
        )}

        <SmartLink
          to="/settings"
          className={`admin-sidebar-user${isActive("/settings") ? " active" : ""}`}
          aria-label={t.settings}
          onClick={onNavigate}
        >
          <div className="admin-sidebar-avatar">
            {avatarUrl ? (
              <img
                src={avatarUrl}
                alt={displayName}
                onError={(event) => {
                  event.currentTarget.style.display = "none";
                }}
              />
            ) : (
              <span>{avatarLetter}</span>
            )}
          </div>

          <div className="admin-sidebar-user-info">
            <strong>{displayName}</strong>
            {displayEmail && <span>{displayEmail}</span>}
          </div>
        </SmartLink>

        <button
          type="button"
          className="admin-sidebar-logout"
          onClick={onLogout}
        >
          <LogOut size={18} />
          <span>{t.logout}</span>
        </button>
      </div>
    </aside>
  );
}