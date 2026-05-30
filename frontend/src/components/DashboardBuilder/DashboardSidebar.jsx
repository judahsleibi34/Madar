import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  Home,
  LayoutDashboard,
  Grid2X2,
  ClipboardList,
  Database,
  CreditCard,
  Settings,
  LogOut,
  Languages,
} from "lucide-react";

import ThemeToggle from "../ThemeChanger/ThemeToggle";
import {
  applyThemeMode,
  readStoredThemeMode,
  normalizeThemeMode,
} from "../../utils/themeMode";

const labels = {
  en: {
    brand: "Madar",
    subtitle: "Admin Panel",
    home: "Home",
    dashboard: "Dashboard",
    pageBuilder: "Page Builder",
    submissions: "Submissions",
    dataLogs: "Data Logs",
    myPlan: "My Plan",
    settings: "Settings",
    language: "العربية",
    logout: "Log out",
    themeMode: "Theme",
  },
  ar: {
    brand: "مدار",
    subtitle: "لوحة التحكم",
    home: "الرئيسية",
    dashboard: "لوحة التحكم",
    pageBuilder: "منشئ الصفحات",
    submissions: "النماذج",
    dataLogs: "سجلات البيانات",
    myPlan: "خطتي",
    settings: "الإعدادات",
    language: "English",
    logout: "تسجيل الخروج",
    themeMode: "الثيم",
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
  compact = false,
  themeMode,
  onThemeModeChange,
}) {
  const navigate = useNavigate();
  const location = useLocation();
  const t = labels[lang] || labels.en;

  const [internalThemeMode, setInternalThemeMode] = useState(() => {
    if (themeMode === "dark" || themeMode === "light") {
      return themeMode;
    }

    return readStoredThemeMode();
  });

  const activeThemeMode =
    themeMode === "dark" || themeMode === "light"
      ? normalizeThemeMode(themeMode)
      : internalThemeMode;

  useEffect(() => {
    applyThemeMode(activeThemeMode);
  }, [activeThemeMode]);

  useEffect(() => {
    const handleThemeStorage = (event) => {
      if (event.key !== "madar-theme-mode") return;

      const nextMode = event.newValue === "dark" ? "dark" : "light";
      setInternalThemeMode(nextMode);
      applyThemeMode(nextMode);
    };

    const handleThemeEvent = (event) => {
      const nextMode = event.detail?.mode === "dark" ? "dark" : "light";
      setInternalThemeMode(nextMode);
    };

    window.addEventListener("storage", handleThemeStorage);
    window.addEventListener("madar-theme-change", handleThemeEvent);

    return () => {
      window.removeEventListener("storage", handleThemeStorage);
      window.removeEventListener("madar-theme-change", handleThemeEvent);
    };
  }, []);

  useEffect(() => {
    if (themeMode === "dark" || themeMode === "light") {
      setInternalThemeMode(themeMode);
      applyThemeMode(themeMode);
    }
  }, [themeMode]);

  const handleThemeChange = (nextMode) => {
    const safeMode = applyThemeMode(nextMode);

    setInternalThemeMode(safeMode);

    if (typeof onThemeModeChange === "function") {
      onThemeModeChange(safeMode);
    }
  };

  const goTo = (path) => {
    navigate(path);

    if (typeof onNavigate === "function") {
      onNavigate();
    }
  };

  const isActive = (path) => {
    if (path === "/") {
      return location.pathname === "/";
    }

    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  const navItemsTop = [
    {
      label: t.home,
      path: "/",
      icon: Home,
    },
    {
      label: t.dashboard,
      path: "/dashboard",
      icon: LayoutDashboard,
    },
    {
      label: t.pageBuilder,
      path: "/page-builder",
      icon: Grid2X2,
    },
    {
      label: t.submissions,
      path: "/builder-responses",
      icon: ClipboardList,
    },
    {
      label: t.dataLogs,
      path: "/builder-data",
      icon: Database,
    },
    {
      label: t.myPlan,
      path: "/my-plan",
      icon: CreditCard,
    },
  ];

  const displayName = user?.name || user?.email || "Madar User";
  const displayEmail = user?.email || "";
  const avatarLetter = displayName.trim().slice(0, 1).toUpperCase() || "M";

  return (
    <aside
      id={id}
      className={`admin-sidebar ${compact ? "is-compact" : ""}`}
      aria-label="Dashboard sidebar"
    >
      <div className="admin-sidebar-top">
        <button
          type="button"
          className="admin-sidebar-brand"
          onClick={() => goTo("/dashboard")}
          title={t.brand}
        >
          <span className="admin-sidebar-icon" aria-hidden="true">
            M
          </span>

          <span className="admin-sidebar-brand-text">
            <strong>{t.brand}</strong>
            <span>{t.subtitle}</span>
          </span>
        </button>

        <nav className="admin-sidebar-nav" aria-label="Dashboard navigation">
          {navItemsTop.map((item) => {
            const Icon = item.icon;

            return (
              <button
                type="button"
                key={item.path}
                className={isActive(item.path) ? "active" : ""}
                onClick={() => goTo(item.path)}
                title={item.label}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}

          <ThemeToggle
            mode={activeThemeMode}
            onChange={handleThemeChange}
            label={t.themeMode}
            compact={compact}
            className="admin-sidebar-theme-row"
          />

          <button
            type="button"
            className={isActive("/settings") ? "active" : ""}
            onClick={() => goTo("/settings")}
            title={t.settings}
          >
            <Settings size={18} />
            <span>{t.settings}</span>
          </button>
        </nav>
      </div>

      <div className="admin-sidebar-bottom">
        {!hideLanguage && typeof onLanguageChange === "function" && (
          <button
            type="button"
            className="admin-sidebar-lang"
            onClick={() => onLanguageChange(lang === "ar" ? "en" : "ar")}
            title={t.language}
          >
            <Languages size={18} />
            <span>{t.language}</span>
          </button>
        )}

        <button
          type="button"
          className="admin-sidebar-logout"
          onClick={onLogout}
          title={t.logout}
        >
          <LogOut size={18} />
          <span>{t.logout}</span>
        </button>

        <div className="admin-sidebar-user" title={displayName}>
          {user?.avatar ? (
            <img
              className="admin-sidebar-avatar"
              src={user.avatar}
              alt={displayName}
            />
          ) : (
            <span className="admin-sidebar-avatar">{avatarLetter}</span>
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