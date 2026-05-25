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
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

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
  },
  ar: {
    responses: "\u0627\u0644\u0631\u062f\u0648\u062f",
    data: "\u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a",
    title: "لوحة التحكم",
    subtitle: "مدار",
    home: "الرئيسية",
    dashboard: "لوحة التحكم",
    pageBuilder: "منشئ الصفحات",
    settings: "الإعدادات",
    logout: "تسجيل الخروج",
    fallbackName: "مستخدم",
    switchLang: "EN",
  },
};

export default function DashboardSidebar({
  lang = "en",
  user,
  onLogout,
  onLanguageChange,
  hideLanguage = false,
}) {
  const navigate = useNavigate();
  const location = useLocation();

  const t = sidebarText[lang] || sidebarText.en;

  const displayName = user?.name || t.fallbackName;
  const displayEmail = user?.email || "";
  const avatarLetter = displayName.trim().charAt(0).toUpperCase() || "U";

  const isActive = (path) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  const handleLangToggle = () => {
    onLanguageChange?.(lang === "en" ? "ar" : "en");
  };

  return (
    <aside className="admin-sidebar">
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
          <button
            type="button"
            className={isActive("/") ? "active" : ""}
            onClick={() => navigate("/")}
          >
            <Home size={18} />
            <span>{t.home}</span>
          </button>

          <button
            type="button"
            className={isActive("/dashboard") ? "active" : ""}
            onClick={() => navigate("/dashboard")}
          >
            <LayoutDashboard size={18} />
            <span>{t.dashboard}</span>
          </button>

          <button
            type="button"
            className={isActive("/page-builder") ? "active" : ""}
            onClick={() => navigate("/page-builder")}
          >
            <PanelsTopLeft size={18} />
            <span>{t.pageBuilder}</span>
          </button>

          <button
            type="button"
            className={isActive("/builder-responses") ? "active" : ""}
            onClick={() => navigate("/builder-responses")}
          >
            <ClipboardList size={18} />
            <span>{t.responses || "Responses"}</span>
          </button>

          <button
            type="button"
            className={isActive("/builder-data") ? "active" : ""}
            onClick={() => navigate("/builder-data")}
          >
            <Database size={18} />
            <span>{t.data || "Data"}</span>
          </button>

          <button
            type="button"
            className={isActive("/settings") ? "active" : ""}
            onClick={() => navigate("/settings")}
          >
            <Settings size={18} />
            <span>{t.settings}</span>
          </button>
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

        <button
          type="button"
          className="admin-sidebar-user"
          onClick={() => navigate("/settings")}
          aria-label={t.settings}
        >
          {user?.avatar ? (
            <img
              className="admin-sidebar-avatar"
              src={user.avatar}
              alt={displayName}
            />
          ) : (
            <div className="admin-sidebar-avatar">{avatarLetter}</div>
          )}

          <div className="admin-sidebar-user-info">
            <strong>{displayName}</strong>
            {displayEmail && <span>{displayEmail}</span>}
          </div>
        </button>

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
