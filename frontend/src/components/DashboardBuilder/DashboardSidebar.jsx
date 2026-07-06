import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Home,
  Archive,
  LayoutDashboard,
  Grid2X2,
  ClipboardList,
  Database,
  CreditCard,
  ShieldCheck,
  Settings,
  LogOut,
  UsersRound,
  KeyRound,
  Search,
} from "lucide-react";

import LanguageSwitcher from "../LanguageSwitcher";
import ThemeToggle from "../ThemeChanger/ThemeToggle";
import NotificationBell from "./NotificationBell";
import {
  applyThemeMode,
  readStoredThemeMode,
  normalizeThemeMode,
} from "../../utils/themeMode";
import { DASHBOARD_ROUTES, PUBLIC_ROUTES } from "../../config/routes";

function normalizeRoleValue(value) {
  return String(value || "").trim().toLowerCase();
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
  showNotifications = false,
}) {
  const { t } = useTranslation(["dashboard"]);
  const navigate = useNavigate();
  const location = useLocation();

  const isRtl = lang === "ar";
  const sidebarDir = isRtl ? "rtl" : "ltr";

  const [internalThemeMode, setInternalThemeMode] = useState(() => {
    if (themeMode === "dark" || themeMode === "light") {
      return themeMode;
    }

    return readStoredThemeMode();
  });
  const [navSearch, setNavSearch] = useState("");

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
      path: PUBLIC_ROUTES.home,
      icon: Home,
    },
    {
      label: t("sidebar.dashboard"),
      path: DASHBOARD_ROUTES.dashboard,
      icon: LayoutDashboard,
    },
    {
      label: t("sidebar.userManagement"),
      path: DASHBOARD_ROUTES.adminUsers,
      icon: UsersRound,
    },
    {
      label: t("sidebar.accountAccess", {
        defaultValue: "Account Access",
      }),
      path: DASHBOARD_ROUTES.adminAccountAccess,
      icon: KeyRound,
    },
  ];

  const userNavItemsTop = [
    {
      label: t("sidebar.home"),
      path: PUBLIC_ROUTES.home,
      icon: Home,
    },
    {
      label: t("sidebar.dashboard"),
      path: DASHBOARD_ROUTES.dashboard,
      icon: LayoutDashboard,
    },
    {
      label: t("sidebar.pageBuilder"),
      path: DASHBOARD_ROUTES.pageBuilder,
      icon: Grid2X2,
    },
    {
      label: t("sidebar.submissions"),
      path: DASHBOARD_ROUTES.builderResponses,
      icon: ClipboardList,
    },
    {
      label: t("sidebar.dataLogs"),
      path: DASHBOARD_ROUTES.builderData,
      icon: Database,
    },
    {
      label: t("sidebar.archive", {
        defaultValue: "Archive",
      }),
      path: DASHBOARD_ROUTES.archive,
      icon: Archive,
    },
    {
      label: t("sidebar.myPlan"),
      path: DASHBOARD_ROUTES.myPlan,
      icon: CreditCard,
    },
  ];

  const visibleNavItemsTop = isAdminUser ? adminNavItemsTop : userNavItemsTop;
  const normalizedNavSearch = navSearch.trim().toLowerCase();
  const filteredNavItemsTop = normalizedNavSearch
    ? visibleNavItemsTop.filter((item) =>
        item.label.toLowerCase().includes(normalizedNavSearch),
      )
    : visibleNavItemsTop;
  const showSettingsLink = true;

  useEffect(() => {
    applyThemeMode(activeThemeMode);
  }, [activeThemeMode]);

  useEffect(() => {
    document.documentElement.dir = isRtl ? "rtl" : "ltr";
    document.documentElement.lang = isRtl ? "ar" : "en";
  }, [isRtl]);

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
    if (path === PUBLIC_ROUTES.home) {
      return location.pathname === PUBLIC_ROUTES.home;
    }

    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  return (
    <aside
      id={id || "dashboard-sidebar"}
      className={`admin-sidebar dashboard-sidebar ${
        compact ? "is-compact" : ""
      } ${isRtl ? "is-rtl" : "is-ltr"}`}
      dir={sidebarDir}
      aria-label={t("sidebar.aria")}
      data-user-role={userRole}
    >
      <div className="admin-sidebar-top">
        <button
          type="button"
          className="admin-sidebar-brand"
          onClick={() => goTo(DASHBOARD_ROUTES.dashboard)}
          title={t("sidebar.brand")}
        >
          <span className="admin-sidebar-icon" aria-hidden="true">
            M
          </span>

          <span className="admin-sidebar-brand-text">
            <strong>{t("sidebar.brand")}</strong>
          </span>
        </button>

        <label className="admin-sidebar-search">
          <Search size={16} aria-hidden="true" />
          <input
            type="search"
            value={navSearch}
            onChange={(event) => setNavSearch(event.target.value)}
            placeholder={t("sidebar.search", {
              defaultValue: "Search...",
            })}
            aria-label={t("sidebar.search", {
              defaultValue: "Search",
            })}
          />
        </label>

        {showNotifications && (
          <NotificationBell
            compact={compact}
            className="admin-sidebar-notifications"
            onNavigate={onNavigate}
          />
        )}

        <nav className="admin-sidebar-nav" aria-label={t("sidebar.navigation")}>
          {filteredNavItemsTop.map((item) => {
            const Icon = item.icon;

            return (
              <button
                type="button"
                key={item.path}
                className={isActive(item.path) ? "active" : ""}
                onClick={() => goTo(item.path)}
                title={item.label}
              >
                <Icon size={18} aria-hidden="true" />
                <span>{item.label}</span>
              </button>
            );
          })}

          <button
            type="button"
            className={isActive(DASHBOARD_ROUTES.settingsSecurity) ? "active" : ""}
            onClick={() => goTo(DASHBOARD_ROUTES.settingsSecurity)}
            title={t("sidebar.security")}
          >
            <ShieldCheck size={18} aria-hidden="true" />
            <span>{t("sidebar.security")}</span>
          </button>
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
          <LogOut size={18} aria-hidden="true" />
          <span>{t("sidebar.logout")}</span>
        </button>

        {showSettingsLink && (
          <button
            type="button"
            className={`admin-sidebar-utility ${
              isActive(DASHBOARD_ROUTES.settings) ? "active" : ""
            }`}
            onClick={() => goTo(DASHBOARD_ROUTES.settings)}
            title={t("sidebar.settings")}
          >
            <Settings size={18} aria-hidden="true" />
            <span>{t("sidebar.settings")}</span>
          </button>
        )}

        <ThemeToggle
          mode={activeThemeMode}
          onChange={handleThemeChange}
          label={t("sidebar.themeMode")}
          compact={compact}
          showLabel
          showSwitch={!compact}
          className="admin-sidebar-theme-row"
        />

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
                  <ShieldCheck size={12} aria-hidden="true" />
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
