import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Home,
  LayoutDashboard,
  Grid2X2,
  ClipboardList,
  Database,
  CreditCard,
  ShieldCheck,
  Settings,
  LogOut,
  UsersRound,
} from "lucide-react";

import LanguageSwitcher from "../LanguageSwitcher";
import ThemeToggle from "../ThemeChanger/ThemeToggle";
import {
  applyThemeMode,
  readStoredThemeMode,
  normalizeThemeMode,
} from "../../utils/themeMode";

function normalizeRoleValue(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

function getUserRole(user) {
  const directRole =
    user?.user_type ||
    user?.role ||
    user?.type ||
    user?.account_type ||
    user?.profile?.user_type ||
    user?.profile?.role ||
    user?.metadata?.user_type ||
    user?.metadata?.role ||
    user?.app_metadata?.user_type ||
    user?.app_metadata?.role ||
    user?.user_metadata?.user_type ||
    user?.user_metadata?.role;

  const normalizedRole = normalizeRoleValue(directRole);

  if (
    normalizedRole === "admin" ||
    normalizedRole === "administrator" ||
    normalizedRole === "super_admin" ||
    normalizedRole === "superadmin"
  ) {
    return "admin";
  }

  if (
    user?.is_admin === true ||
    user?.isAdmin === true ||
    user?.admin === true ||
    user?.profile?.is_admin === true ||
    user?.profile?.isAdmin === true ||
    user?.metadata?.is_admin === true ||
    user?.metadata?.isAdmin === true ||
    user?.app_metadata?.is_admin === true ||
    user?.app_metadata?.isAdmin === true ||
    user?.user_metadata?.is_admin === true ||
    user?.user_metadata?.isAdmin === true
  ) {
    return "admin";
  }

  return "user";
}

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
  const { t } = useTranslation(["dashboard"]);
  const navigate = useNavigate();
  const location = useLocation();

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

  const displayName = user?.name || user?.email || t("user.fallbackName");
  const displayEmail = user?.email || "";

  const userRole = useMemo(() => getUserRole(user), [user]);
  const isAdminUser = userRole === "admin";

  const avatarLetter = displayName.trim().slice(0, 1).toUpperCase() || "M";

  const adminNavItemsTop = [
    {
      label: t("sidebar.home"),
      path: "/",
      icon: Home,
    },
    {
      label: t("sidebar.dashboard"),
      path: "/dashboard",
      icon: LayoutDashboard,
    },
    {
      label: t("sidebar.userManagement"),
      path: "/admin/users",
      icon: UsersRound,
    },
  ];

  const userNavItemsTop = [
    {
      label: t("sidebar.home"),
      path: "/",
      icon: Home,
    },
    {
      label: t("sidebar.dashboard"),
      path: "/dashboard",
      icon: LayoutDashboard,
    },
    {
      label: t("sidebar.pageBuilder"),
      path: "/page-builder",
      icon: Grid2X2,
    },
    {
      label: t("sidebar.submissions"),
      path: "/builder-responses",
      icon: ClipboardList,
    },
    {
      label: t("sidebar.dataLogs"),
      path: "/builder-data",
      icon: Database,
    },
    {
      label: t("sidebar.myPlan"),
      path: "/my-plan",
      icon: CreditCard,
    },
  ];

  const visibleNavItemsTop = isAdminUser ? adminNavItemsTop : userNavItemsTop;
  const showSettingsLink = !isAdminUser;

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

  return (
    <aside
      id={id}
      className={`admin-sidebar ${compact ? "is-compact" : ""}`}
      aria-label={t("sidebar.aria")}
      data-user-role={userRole}
    >
      <div className="admin-sidebar-top">
        <button
          type="button"
          className="admin-sidebar-brand"
          onClick={() => goTo("/dashboard")}
          title={t("sidebar.brand")}
        >
          <span className="admin-sidebar-icon" aria-hidden="true">
            M
          </span>

          <span className="admin-sidebar-brand-text">
            <strong>{t("sidebar.brand")}</strong>
            <span>
              {isAdminUser
                ? t("sidebar.subtitle")
                : t("sidebar.userSubtitle", {
                    defaultValue: "Workspace",
                  })}
            </span>
          </span>
        </button>

        <nav className="admin-sidebar-nav" aria-label={t("sidebar.navigation")}>
          {visibleNavItemsTop.map((item) => {
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
            label={t("sidebar.themeMode")}
            compact
            showLabel
            showSwitch={false}
            className="admin-sidebar-theme-row"
          />

          {showSettingsLink && (
            <button
              type="button"
              className={isActive("/settings") ? "active" : ""}
              onClick={() => goTo("/settings")}
              title={t("sidebar.settings")}
            >
              <Settings size={18} />
              <span>{t("sidebar.settings")}</span>
            </button>
          )}
        </nav>
      </div>

      <div className="admin-sidebar-bottom">
        {!hideLanguage && typeof onLanguageChange === "function" && (
          <LanguageSwitcher
            current={lang}
            onChange={onLanguageChange}
            compact={compact}
            className="admin-sidebar-lang-switcher"
          />
        )}

        <button
          type="button"
          className="admin-sidebar-logout"
          onClick={onLogout}
          title={t("sidebar.logout")}
        >
          <LogOut size={18} />
          <span>{t("sidebar.logout")}</span>
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
            <div className="admin-sidebar-user-meta-row">
              {isAdminUser ? (
                <span
                  className="admin-sidebar-admin-badge"
                  title={t("sidebar.admin")}
                >
                  <ShieldCheck size={12} />
                  {t("sidebar.admin")}
                </span>
              ) : (
                <span
                  className="admin-sidebar-admin-badge"
                  title={t("sidebar.userRole", {
                    defaultValue: "User",
                  })}
                >
                  {t("sidebar.userRole", {
                    defaultValue: "User",
                  })}
                </span>
              )}
            </div>

            <div className="admin-sidebar-user-title-row">
              <strong>{displayName}</strong>
            </div>

            {displayEmail && <span>{displayEmail}</span>}
          </div>
        </div>
      </div>
    </aside>
  );
}