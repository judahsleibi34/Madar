import {
  Home,
  LayoutDashboard,
  PanelsTopLeft,
  Settings,
  LogOut,
  Grid2X2,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

const sidebarText = {
  en: {
    title: "Dashboard",
    subtitle: "Madar",
    home: "Home",
    dashboard: "Dashboard",
    pageBuilder: "Page Builder",
    settings: "Settings",
    logout: "Logout",
    fallbackName: "User",
  },

  ar: {
    title: "لوحة التحكم",
    subtitle: "مدار",
    home: "الرئيسية",
    dashboard: "لوحة التحكم",
    pageBuilder: "منشئ الصفحات",
    settings: "الإعدادات",
    logout: "تسجيل الخروج",
    fallbackName: "مستخدم",
  },
};

export default function DashboardSidebar({ lang = "en", user, onLogout }) {
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

          <button type="button">
            <Settings size={18} />
            <span>{t.settings}</span>
          </button>
        </nav>
      </div>

      <div className="admin-sidebar-bottom">
        <button type="button" className="admin-sidebar-logout" onClick={onLogout}>
          <LogOut size={18} />
          <span>{t.logout}</span>
        </button>

        <div className="admin-sidebar-user">
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
        </div>
      </div>
    </aside>
  );
}