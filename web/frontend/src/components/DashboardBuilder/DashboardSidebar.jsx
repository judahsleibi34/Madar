import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Home,
  GraduationCap,
  BookOpen,
  Users,
  Archive,
  LayoutDashboard,
  GalleryHorizontalEnd,
  PanelsTopLeft,
  LayoutTemplate,
  Globe,
  ClipboardList,
  CalendarDays,
  Database,
  CreditCard,
  Gift,
  Badge,
  FolderTree,
  FileSearch,
  Package,
  MapPin,
  Palette,
  ShoppingBag,
  Share2,
  Tag,
  ShieldCheck,
  Settings,
  LogOut,
  ChevronDown,
  PanelLeftClose,
  PanelLeftOpen,
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

function SidebarRow({
  active = false,
  controls,
  expanded,
  icon: Icon,
  label,
  onClick,
  path,
}) {
  const expandable = typeof expanded === "boolean";

  return (
    <button
      type="button"
      className={`admin-sidebar-row ${
        active && !expandable ? "active" : ""
      }`.trim()}
      onClick={onClick}
      title={label}
      aria-current={!expandable && active ? "page" : undefined}
      aria-expanded={expandable ? expanded : undefined}
      aria-controls={expandable ? controls : undefined}
      data-sidebar-path={path}
      data-route-path={path}
    >
      <Icon className="admin-sidebar-row-icon" size={18} aria-hidden="true" />
      <span className="admin-sidebar-row-label">{label}</span>
      {expandable && (
        <ChevronDown
          className="admin-sidebar-chevron"
          size={17}
          aria-hidden="true"
        />
      )}
    </button>
  );
}

export default function DashboardSidebar({
  id,
  lang = "en",
  user,
  onLogout,
  onLanguageChange,
  onNavigate,
  hideLanguage = false,
  themeMode,
  onThemeModeChange,
  showNotifications = false,
}) {
  const { t, i18n } = useTranslation(["dashboard"]);
  const isPlatformAdmin = user?.account_kind === "platform" && user?.user_type === "admin";
  const navigate = useNavigate();
  const location = useLocation();
  const sidebarRef = useRef(null);

  const activeSidebarLanguage =
    i18n?.resolvedLanguage?.split("-")[0] || lang;
  const isRtl = activeSidebarLanguage === "ar";
  const sidebarDir = isRtl ? "rtl" : "ltr";

  const [internalThemeMode, setInternalThemeMode] = useState(() => {
    if (themeMode === "dark" || themeMode === "light") {
      return themeMode;
    }

    return readStoredThemeMode();
  });

  const workspaceRouteActive = [
    DASHBOARD_ROUTES.pageBuilder,
    DASHBOARD_ROUTES.builderResponses,
    DASHBOARD_ROUTES.builderData,
    DASHBOARD_ROUTES.calendar,
    DASHBOARD_ROUTES.agenda,
    DASHBOARD_ROUTES.archive,
  ].some(
    (path) =>
      location.pathname === path ||
      location.pathname.startsWith(`${path}/`),
  );
  const settingsRouteActive =
    location.pathname === DASHBOARD_ROUTES.settings ||
    location.pathname.startsWith(DASHBOARD_ROUTES.settings + "/");
  const ecommerceRouteActive = [
    DASHBOARD_ROUTES.ecommerceTags,
    DASHBOARD_ROUTES.ecommerceCategories,
    DASHBOARD_ROUTES.ecommerceBrands,
    DASHBOARD_ROUTES.ecommerceProducts,
    DASHBOARD_ROUTES.ecommerceDelivery,
    DASHBOARD_ROUTES.ecommerceOrders,
    DASHBOARD_ROUTES.ecommerceLanding,
    DASHBOARD_ROUTES.ecommerceTheme,
    DASHBOARD_ROUTES.ecommerceStore,
  ].some(
    (path) =>
      location.pathname === path ||
      location.pathname.startsWith(`${path}/`),
  );
  const elearningRouteActive = location.pathname === DASHBOARD_ROUTES.elearning ||
    location.pathname.startsWith(`${DASHBOARD_ROUTES.elearning}/`);
  const [elearningExpansion, setELearningExpansion] = useState({
    open: elearningRouteActive,
    pathname: location.pathname,
  });
  const [workspaceExpansion, setWorkspaceExpansion] = useState({
    open: workspaceRouteActive,
    pathname: location.pathname,
  });
  const [ecommerceExpansion, setEcommerceExpansion] = useState({
    open: ecommerceRouteActive,
    pathname: location.pathname,
  });
  const [settingsExpansion, setSettingsExpansion] = useState({
    open: settingsRouteActive,
    pathname: location.pathname,
  });
  const compactSidebarRouteActive = workspaceRouteActive ||
    /^\/e-learning\/landing-page\/projects\/[^/]+(?:\/|$)/.test(location.pathname);
  const [workspaceSidebarCollapsed, setWorkspaceSidebarCollapsed] =
    useState(true);
  const [previousCompactRouteActive, setPreviousCompactRouteActive] = useState(compactSidebarRouteActive);
  if (previousCompactRouteActive !== compactSidebarRouteActive) {
    setPreviousCompactRouteActive(compactSidebarRouteActive);
    setWorkspaceSidebarCollapsed(true);
  }
  const isWorkspaceSidebarCollapsed =
    compactSidebarRouteActive && workspaceSidebarCollapsed;

  useEffect(() => {
    if (!compactSidebarRouteActive || isWorkspaceSidebarCollapsed) return undefined;

    const handleOutsidePointerDown = (event) => {
      if (sidebarRef.current?.contains(event.target)) return;
      setWorkspaceSidebarCollapsed(true);
    };

    document.addEventListener("pointerdown", handleOutsidePointerDown);
    return () => {
      document.removeEventListener("pointerdown", handleOutsidePointerDown);
    };
  }, [isWorkspaceSidebarCollapsed, compactSidebarRouteActive]);

  const activeThemeMode =
    themeMode === "dark" || themeMode === "light"
      ? normalizeThemeMode(themeMode)
      : internalThemeMode;

  const displayName = user?.name || user?.email || t("user.fallbackName");
  const displayEmail = user?.email || "";

  const userRole = useMemo(() => getUserRole(user), [user]);
  const isAdminUser = userRole === "admin";

  const avatarLetter = displayName.trim().slice(0, 1).toUpperCase() || "M";

  const primaryNavItems = [
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
      label: t("sidebar.cvRerank", { defaultValue: "CV Rerank" }),
      path: DASHBOARD_ROUTES.ecommerceCvRerank,
      icon: FileSearch,
    },
    {
      label: t("sidebar.myPlan"),
      path: DASHBOARD_ROUTES.myPlan,
      icon: CreditCard,
    },
];

  const workspaceItems = [
    {
      label: t("sidebar.pageBuilder"),
      path: DASHBOARD_ROUTES.pageBuilder,
      icon: PanelsTopLeft,
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
      label: t("sidebar.calendar", { defaultValue: "Calendar" }),
      path: DASHBOARD_ROUTES.calendar,
      icon: CalendarDays,
    },
    {
      label: t("sidebar.archive", { defaultValue: "Archive" }),
      path: DASHBOARD_ROUTES.archive,
      icon: Archive,
    },
  ];
  const ecommerceItems = [
    {
      label: t("sidebar.tags", { defaultValue: "Tags" }),
      path: DASHBOARD_ROUTES.ecommerceTags,
      icon: Tag,
    },
    {
      label: t("sidebar.categories", { defaultValue: "Categories" }),
      path: DASHBOARD_ROUTES.ecommerceCategories,
      icon: FolderTree,
    },
    {
      label: t("sidebar.brands", { defaultValue: "Brands" }),
      path: DASHBOARD_ROUTES.ecommerceBrands,
      icon: Badge,
    },
    {
      label: t("sidebar.products", { defaultValue: "Products" }),
      path: DASHBOARD_ROUTES.ecommerceProducts,
      icon: Package,
    },
    {
      label: t("sidebar.delivery", { defaultValue: "Delivery" }),
      path: DASHBOARD_ROUTES.ecommerceDelivery,
      icon: MapPin,
    },
    {
      label: t("sidebar.orders", { defaultValue: "Orders" }),
      path: DASHBOARD_ROUTES.ecommerceOrders,
      icon: ClipboardList,
    },
    {
      label: t("sidebar.loyalty", { defaultValue: "Loyalty" }),
      path: DASHBOARD_ROUTES.ecommerceLoyalty,
      icon: Gift,
    },
    {
      label: t("sidebar.landingPage", { defaultValue: "Landing page" }),
      path: DASHBOARD_ROUTES.ecommerceLanding,
      icon: GalleryHorizontalEnd,
    },
    {
      label: t("sidebar.storeTheme", { defaultValue: "Store theme" }),
      path: DASHBOARD_ROUTES.ecommerceTheme,
      icon: Palette,
    },
    {
      label: t("sidebar.socialLinks", { defaultValue: "Social links" }),
      path: DASHBOARD_ROUTES.ecommerceSocialLinks,
      icon: Share2,
    },
    {
      label: t("sidebar.store", { defaultValue: "Store" }),
      path: DASHBOARD_ROUTES.ecommerceStore,
      icon: ShoppingBag,
    },
  ];
  const elearningItems = [
    { label: t("sidebar.elearningCourses", { defaultValue: "Courses" }), path: DASHBOARD_ROUTES.elearningCourses, icon: BookOpen },
    { label: t("sidebar.elearningGroups", { defaultValue: "Groups" }), path: DASHBOARD_ROUTES.elearningGroups, icon: Users },
    { label: t("sidebar.elearningInstructors", { defaultValue: "Instructors" }), path: DASHBOARD_ROUTES.elearningInstructors, icon: GraduationCap },
    { label: t("elearning.academy.learningPlans"), path: DASHBOARD_ROUTES.elearningPlans, icon: CreditCard },
    { label: t("elearning.academy.landingPage"), path: "/e-learning/landing-page", icon: LayoutTemplate },
    { label: t("elearning.academy.academyAccess"), path: "/e-learning/academy-access", icon: Globe },
    { label: t("sidebar.settings"), path: DASHBOARD_ROUTES.elearningSettings, icon: Settings },
  ];

  const workspaceLabel = t("sidebar.workspace", {
    defaultValue: "Workspace",
  });
  const workspaceIsExpanded =
    workspaceExpansion.pathname === location.pathname
      ? workspaceExpansion.open
      : workspaceRouteActive;
  const elearningIsExpanded = elearningExpansion.pathname === location.pathname
    ? elearningExpansion.open : elearningRouteActive;
  const ecommerceIsExpanded = ecommerceExpansion.open;
  const settingsIsExpanded =
    settingsExpansion.pathname === location.pathname
      ? settingsExpansion.open
      : settingsRouteActive;

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

  const expandWorkspaceSidebar = () => {
    if (isWorkspaceSidebarCollapsed) {
      setWorkspaceSidebarCollapsed(false);
    }
  };

  const toggleSettings = () => {
    const nextOpen = isWorkspaceSidebarCollapsed || !settingsIsExpanded;

    if (isWorkspaceSidebarCollapsed) {
      setWorkspaceSidebarCollapsed(false);
    }

    setSettingsExpansion({
      open: nextOpen,
      pathname: location.pathname,
    });

    if (nextOpen) {
      setELearningExpansion({ open: false, pathname: location.pathname });
      setWorkspaceExpansion({
        open: false,
        pathname: location.pathname,
      });
      setEcommerceExpansion({
        open: false,
        pathname: location.pathname,
      });
    }
  };

  const isActive = (path) => {
    if (path === "/my-learning") {
      return location.pathname === path || location.pathname.startsWith(`${path}/courses/`);
    }
    if (path === PUBLIC_ROUTES.home) {
      return location.pathname === PUBLIC_ROUTES.home;
    }

    if (path === DASHBOARD_ROUTES.calendar) {
      return (
        location.pathname === DASHBOARD_ROUTES.calendar ||
        location.pathname.startsWith(`${DASHBOARD_ROUTES.calendar}/`) ||
        location.pathname === DASHBOARD_ROUTES.agenda ||
        location.pathname.startsWith(`${DASHBOARD_ROUTES.agenda}/`)
      );
    }

    return location.pathname === path || location.pathname.startsWith(`${path}/`);
  };

  return (
    <aside
      ref={sidebarRef}
      id={id || "dashboard-sidebar"}
      className={`admin-sidebar dashboard-sidebar global-sidebar ${
        isRtl ? "is-rtl" : "is-ltr"
      } ${isWorkspaceSidebarCollapsed ? "is-workspace-collapsed" : ""}`.trim()}
      dir={sidebarDir}
      aria-label={t("sidebar.aria")}
      data-user-role={userRole}
    >
      <div className="dashboard-sidebar-skeleton" aria-hidden="true">
        <div className="dashboard-sidebar-skeleton-brand"><i /><i /></div>
        {Array.from({ length: 13 }, (_, index) => (
          <div key={index} className={`dashboard-sidebar-skeleton-row ${index >= 5 && index <= 11 ? "is-nested" : ""}`}>
            <i /><i />
          </div>
        ))}
      </div>
      <div className="admin-sidebar-top">
        <div className="admin-sidebar-brand-row">
          <button
            type="button"
            className="admin-sidebar-brand"
            data-route-path={DASHBOARD_ROUTES.dashboard}
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

          {compactSidebarRouteActive && (
            <button
              type="button"
              className="admin-sidebar-workspace-collapse"
              onClick={() =>
                setWorkspaceSidebarCollapsed((collapsed) => !collapsed)
              }
              aria-label={
                isWorkspaceSidebarCollapsed
                  ? t("sidebar.expand", { defaultValue: "Expand sidebar" })
                  : t("sidebar.collapse", { defaultValue: "Collapse sidebar" })
              }
              aria-expanded={!isWorkspaceSidebarCollapsed}
              title={
                isWorkspaceSidebarCollapsed
                  ? t("sidebar.expand", { defaultValue: "Expand sidebar" })
                  : t("sidebar.collapse", { defaultValue: "Collapse sidebar" })
              }
            >
              {isWorkspaceSidebarCollapsed ? (
                <PanelLeftOpen size={17} aria-hidden="true" />
              ) : (
                <PanelLeftClose size={17} aria-hidden="true" />
              )}
            </button>
          )}
        </div>

        <nav
          className="admin-sidebar-nav"
          aria-label={t("sidebar.navigation")}
          onClickCapture={expandWorkspaceSidebar}
        >
          {!isPlatformAdmin && showNotifications && (
            <NotificationBell
              className="admin-sidebar-notifications"
              onNavigate={onNavigate}
            />
          )}

          {(isPlatformAdmin ? [
            { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
            { path: "/admin/users", label: "Users / Tenants", icon: ShieldCheck },
            { path: "/admin/account-access", label: "Account Access", icon: ShieldCheck },
            { path: "/settings/security", label: "Security", icon: ShieldCheck },
          ] : primaryNavItems.slice(0, 2)).map((item) => {
            const active = isActive(item.path);

            return (
              <SidebarRow
                key={item.path}
                active={active}
                icon={item.icon}
                label={item.label}
                onClick={() => goTo(item.path)}
                path={item.path}
              />
            );
          })}

          {!isPlatformAdmin && <div className="admin-sidebar-group">
            <SidebarRow
                controls="dashboard-sidebar-workspace"
                expanded={workspaceIsExpanded}
                icon={PanelsTopLeft}
                label={workspaceLabel}
                onClick={() => {
                  const nextOpen = !workspaceIsExpanded;

                  setWorkspaceExpansion({
                    open: nextOpen,
                    pathname: location.pathname,
                  });

                  if (nextOpen) {
                    setELearningExpansion({ open: false, pathname: location.pathname });
                    setEcommerceExpansion({
                      open: false,
                      pathname: location.pathname,
                    });
                    setSettingsExpansion({
                      open: false,
                      pathname: location.pathname,
                    });
                  }
                }}
              />

            {workspaceIsExpanded && (
                <div
                  className="admin-sidebar-subnav"
                  id="dashboard-sidebar-workspace"
                >
                  {workspaceItems.map((item) => {
                    const Icon = item.icon;
                    const active = isActive(item.path);

                    return (
                      <button
                        type="button"
                        key={item.path}
                        className={active ? "active" : ""}
                        data-route-path={item.path}
                onClick={() => goTo(item.path)}
                        title={item.label}
                        aria-current={active ? "page" : undefined}
                      >
                        <Icon size={16} aria-hidden="true" />
                        <span>{item.label}</span>
                      </button>
                    );
                  })}
                </div>
              )}
          </div>}

          {!isPlatformAdmin && <div className="admin-sidebar-group">
            <SidebarRow
              controls="dashboard-sidebar-ecommerce"
              expanded={ecommerceIsExpanded}
              icon={ShoppingBag}
              label={t("sidebar.ecommerce", { defaultValue: "Online Store" })}
              onClick={() => {
                const nextOpen = !ecommerceIsExpanded;

                setEcommerceExpansion({
                  open: nextOpen,
                  pathname: location.pathname,
                });

                if (nextOpen) {
                  setELearningExpansion({ open: false, pathname: location.pathname });
                  setWorkspaceExpansion({
                    open: false,
                    pathname: location.pathname,
                  });
                  setSettingsExpansion({
                    open: false,
                    pathname: location.pathname,
                  });
                }
              }}
            />

            {ecommerceIsExpanded && (
              <div
                className="admin-sidebar-subnav"
                id="dashboard-sidebar-ecommerce"
              >
                {ecommerceItems.map((item) => {
                  const Icon = item.icon;
                  const active = isActive(item.path);

                  return (
                    <Link
                      to={item.path}
                      key={item.path}
                      className={active ? "active" : ""}
                      onClick={() => {
                        if (typeof onNavigate === "function") onNavigate();
                      }}
                      title={item.label}
                      aria-current={active ? "page" : undefined}
                    >
                      <Icon size={16} aria-hidden="true" />
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>}

          {!isPlatformAdmin && <div className="admin-sidebar-group">
            <SidebarRow
              controls="dashboard-sidebar-elearning"
              expanded={elearningIsExpanded}
              icon={GraduationCap}
              label={t("sidebar.elearning")}
              onClick={() => {
                const nextOpen = !elearningIsExpanded;
                setELearningExpansion({ open: nextOpen, pathname: location.pathname });
                if (nextOpen) {
                  setWorkspaceExpansion({ open: false, pathname: location.pathname });
                  setEcommerceExpansion({ open: false, pathname: location.pathname });
                  setSettingsExpansion({ open: false, pathname: location.pathname });
                }
              }}
            />
            {elearningIsExpanded && <div className="admin-sidebar-subnav" id="dashboard-sidebar-elearning">
              {elearningItems.map((item) => {
                const Icon = item.icon;
                const active = item.path === "/e-learning/academy-access"
                  ? isActive(item.path) || isActive("/e-learning/settings/academy")
                  : item.path === DASHBOARD_ROUTES.elearningSettings
                    ? location.pathname === item.path
                    : isActive(item.path);
                return <Link key={item.path} to={item.path} className={active ? "active" : ""}
                  aria-current={active ? "page" : undefined} title={item.label}
                  onClick={() => { if (typeof onNavigate === "function") onNavigate(); }}>
                  <Icon size={16} aria-hidden="true" /><span>{item.label}</span>
                </Link>;
              })}
            </div>}
          </div>}

          {!isPlatformAdmin && primaryNavItems.slice(2).map((item) => {
            const active = isActive(item.path);

            return (
              <SidebarRow
                key={item.path}
                active={active}
                icon={item.icon}
                label={item.label}
                onClick={() => goTo(item.path)}
                path={item.path}
              />
            );
          })}
        </nav>
      </div>

      <div className="admin-sidebar-bottom">
        <div
          className="admin-sidebar-group admin-sidebar-settings-group"
        >
          <SidebarRow
            controls="dashboard-sidebar-settings"
            expanded={settingsIsExpanded}
            icon={Settings}
            label={t("sidebar.settings")}
            onClick={toggleSettings}
          />

          {settingsIsExpanded && (
            <div
              className="admin-sidebar-subnav admin-sidebar-settings-subnav"
              id="dashboard-sidebar-settings"
            >
              {!hideLanguage && typeof onLanguageChange === "function" && (
                <div className="admin-sidebar-language-item">
                  <LanguageSwitcher
                    current={activeSidebarLanguage}
                    onChange={onLanguageChange}
                    className="admin-sidebar-lang-switcher"
                    label={t("sidebar.language", { defaultValue: "Language" })}
                  />

                </div>
              )}

              <button
                type="button"
                className={`admin-sidebar-utility ${
                  settingsRouteActive ? "active" : ""
                }`}
                data-route-path={DASHBOARD_ROUTES.settings}
                onClick={() => goTo(DASHBOARD_ROUTES.settings)}
                title={t("sidebar.settings")}
                aria-current={settingsRouteActive ? "page" : undefined}
              >
                <Settings size={16} aria-hidden="true" />
                <span>{t("sidebar.settings")}</span>
              </button>

              <ThemeToggle
                mode={activeThemeMode}
                onChange={handleThemeChange}
                label={t("sidebar.themeMode")}
                showLabel
                showSwitch
                className="admin-sidebar-theme-row"
              />

              <button
                type="button"
                className="admin-sidebar-logout"
                onClick={onLogout}
                title={t("sidebar.logout")}
              >
                <LogOut size={16} aria-hidden="true" />
                <span>{t("sidebar.logout")}</span>
              </button>
            </div>
          )}
        </div>

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
            <div className="admin-sidebar-user-title-row">
              <strong>{displayName}</strong>
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
            </div>

            {displayEmail && <span>{displayEmail}</span>}
          </div>
        </div>
      </div>
    </aside>
  );
}
