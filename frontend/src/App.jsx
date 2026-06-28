import { useCallback, useEffect, useState } from "react";
import {
  Routes,
  Route,
  useNavigate,
  Navigate,
  useLocation,
} from "react-router-dom";
import { Menu, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import TeamPage from "./components/MainPages/TeamPage";
import Header from "./components/MainPages/Header";
import HeroSection from "./components/MainPages/HeroSection";
import AboutSection from "./components/MainPages/AboutSection";
import ContactPage from "./components/MainPages/ContactPage";
import FeaturesPage from "./components/MainPages/FeaturesPage";
import PricingPage from "./components/MainPages/PricingPage";
import Footer from "./components/MainPages/Footer";

import LoginPage from "./components/AuthPages/LoginPage";
import SignUpPage from "./components/AuthPages/SignUpPage";
import ForgotPasswordPage from "./components/AuthPages/ForgotPasswordPage";
import ResetPasswordPage from "./components/AuthPages/ResetPasswordPage";

import Dashboard from "./components/DashboardBuilder/Dashboard";
import DashboardSidebar from "./components/DashboardBuilder/DashboardSidebar";
import ScrollToTop from "./components/DashboardBuilder/ScrollToTop";
import SettingsPage from "./components/DashboardBuilder/SettingsPage";
import ChangePasswordPage from "./components/DashboardBuilder/ChangePasswordPage";
import UserManagementPage from "./components/DashboardBuilder/UserManagementPage";
import UserDashboard from "./components/DashboardBuilder/UserDashboard";
import MyPlanPage from "./components/MainPages/MyPlanPage";

import PageBuilder from "./components/PageBuilder";
import BuilderFormPreviewPage from "./components/PageBuilder/preview/BuilderFormPreviewPage";
import TenantSiteRuntime from "./components/PageBuilder/runtime/TenantSiteRuntime";

import { applyThemeMode, readStoredThemeMode } from "./utils/themeMode";
import {
  apiFetch,
  clearCsrfToken,
  syncCsrfTokenFromResponseData,
} from "./utils/apiClient";
import { getCurrentLanguage, setAppLanguage } from "./i18n/language";
import { appShellContent } from "./content";

import "./components/DashboardBuilder/DashboardShellFix.css";

const API_URL = import.meta.env.VITE_API_URL || "/api";

let authBootstrapPromise = null;

function normalizeUserType(value) {
  return String(value || "user").trim().toLowerCase();
}

function RestrictedAccessWindow({
  title = appShellContent.restrictedAccess.title,
  message = appShellContent.restrictedAccess.defaultMessage,
  actionLabel = appShellContent.restrictedAccess.actionLabel,
  onAction,
}) {
  return (
    <section className="restricted-access-page">
      <div className="restricted-access-card" role="status">
        <div className="restricted-access-content">
          <p className="restricted-access-eyebrow">{title}</p>
          <h1>{title}</h1>
          <p>{message}</p>
        </div>

        <button type="button" onClick={onAction}>
          {actionLabel}
        </button>
      </div>
    </section>
  );
}

export default function App() {
  const { t, i18n } = useTranslation(["auth", "dashboard", "common"]);
  const [lang, setLang] = useState(getCurrentLanguage);
  const [themeMode, setThemeMode] = useState(readStoredThemeMode);

  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [user, setUser] = useState(null);
  const [dashboardSidebarOpen, setDashboardSidebarOpen] = useState(false);

  const navigate = useNavigate();
  const location = useLocation();

  const normalizedUserType = normalizeUserType(user?.user_type);
  const isAdminUser = normalizedUserType === "admin";
  const isRegularUser = !isAdminUser;

  const isTenantSiteRoute = location.pathname.startsWith("/site/");

  const isDashboardRoute =
    location.pathname.startsWith("/dashboard") ||
    location.pathname.startsWith("/page-builder") ||
    location.pathname.startsWith("/builder-responses") ||
    location.pathname.startsWith("/builder-data") ||
    location.pathname.startsWith("/my-plan") ||
    location.pathname.startsWith("/admin/users") ||
    location.pathname.startsWith("/settings");

  const getCurrentReturnTo = () =>
    encodeURIComponent(
      `${location.pathname}${location.search}${location.hash}`
    );

  const normalizeUser = useCallback((userInfo) => {
    const firstName = userInfo?.first_name || "";
    const lastName = userInfo?.last_name || "";
    const fullName =
      userInfo?.name ||
      `${firstName} ${lastName}`.trim() ||
      userInfo?.username ||
      appShellContent.user.fallbackName;

    return {
      id: userInfo?.id || "",
      auth_id: userInfo?.auth_id || "",
      tenant_id: userInfo?.tenant_id || "",
      first_name: firstName,
      last_name: lastName,
      name: fullName,
      email: userInfo?.email || "",
      phone: userInfo?.phone || "",
      avatar: userInfo?.avatar || userInfo?.avatar_url || "",
      subscription_type: userInfo?.subscription_type || "",
      plan: userInfo?.plan || "",
      builder_type: userInfo?.builder_type || "",
      features: Array.isArray(userInfo?.features) ? userInfo.features : [],
      payment_status: userInfo?.payment_status || "",
      user_type: normalizeUserType(userInfo?.user_type),
      created_at: userInfo?.created_at || "",
      updated_at: userInfo?.updated_at || "",
    };
  }, []);

  const fetchUserInfo = useCallback(async () => {
    const response = await apiFetch(`${API_URL}/auth/user_status`, {
      method: "GET",
      cache: "no-store",
    });

    if (response.status === 401 || response.status === 403) {
      return null;
    }

    if (!response.ok) {
      const error = new Error(appShellContent.errors.fetchUserInfo);
      error.status = response.status;
      throw error;
    }

    const data = await response.json();
    syncCsrfTokenFromResponseData(data);
    return normalizeUser(data.user || data);
  }, [normalizeUser]);

  const refreshAuthSession = useCallback(async () => {
    const response = await apiFetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      cache: "no-store",
    });

    if (!response.ok) return null;

    const data = await response.json();
    syncCsrfTokenFromResponseData(data);

    const loggedIn =
      data.logged_in === true || data.authenticated === true;

    if (!loggedIn || !data.user) return null;

    return normalizeUser(data.user);
  }, [normalizeUser]);

  const bootstrapAuth = useCallback(async () => {
    try {
      const statusResponse = await apiFetch(`${API_URL}/auth/user_status`, {
        method: "GET",
        cache: "no-store",
      });

      if (statusResponse.status === 401 || statusResponse.status === 403) {
        return {
          loggedIn: false,
          user: null,
        };
      }

      if (!statusResponse.ok) {
        return {
          loggedIn: false,
          user: null,
        };
      }

      const statusData = await statusResponse.json();
      syncCsrfTokenFromResponseData(statusData);

      const loggedIn =
        statusData.logged_in === true || statusData.authenticated === true;

      if (!loggedIn) {
        const refreshedUser = await refreshAuthSession();
        if (refreshedUser?.id) {
          return {
            loggedIn: true,
            user: refreshedUser,
          };
        }

        return {
          loggedIn: false,
          user: null,
        };
      }

      const userInfo = normalizeUser(statusData.user || statusData);

      if (!userInfo?.id) {
        const refreshedUser = await refreshAuthSession();
        if (refreshedUser?.id) {
          return {
            loggedIn: true,
            user: refreshedUser,
          };
        }

        return {
          loggedIn: false,
          user: null,
        };
      }

      return {
        loggedIn: true,
        user: userInfo,
      };
    } catch (error) {
      console.error("Auth check failed:", error);

      return {
        loggedIn: false,
        user: null,
      };
    }
  }, [normalizeUser, refreshAuthSession]);

  useEffect(() => {
    const safeLanguage = lang === "ar" ? "ar" : "en";
    const direction = safeLanguage === "ar" ? "rtl" : "ltr";

    document.documentElement.lang = safeLanguage;
    document.documentElement.dir = direction;
    document.body.dir = direction;

    setAppLanguage(safeLanguage);
  }, [lang]);

  useEffect(() => {
    const handleI18nLanguageChange = (nextLanguage) => {
      const safeLanguage = nextLanguage?.split("-")[0] === "ar" ? "ar" : "en";
      setLang(safeLanguage);
    };

    i18n.on("languageChanged", handleI18nLanguageChange);

    return () => {
      i18n.off("languageChanged", handleI18nLanguageChange);
    };
  }, [i18n]);

  useEffect(() => {
    applyThemeMode(themeMode);
  }, [themeMode]);

  useEffect(() => {
    const closeSidebarTimer = window.setTimeout(() => {
      setDashboardSidebarOpen(false);
    }, 0);

    return () => {
      window.clearTimeout(closeSidebarTimer);
    };
  }, [location.pathname]);

  useEffect(() => {
    const handleThemeEvent = (event) => {
      const nextMode = event.detail?.mode === "dark" ? "dark" : "light";
      setThemeMode(nextMode);
    };

    const handleStorage = (event) => {
      if (event.key !== "madar-theme-mode") return;
      setThemeMode(event.newValue === "dark" ? "dark" : "light");
    };

    window.addEventListener("madar-theme-change", handleThemeEvent);
    window.addEventListener("storage", handleStorage);

    return () => {
      window.removeEventListener("madar-theme-change", handleThemeEvent);
      window.removeEventListener("storage", handleStorage);
    };
  }, []);

  const handleThemeModeChange = useCallback((nextMode) => {
    const safeMode = applyThemeMode(nextMode);
    setThemeMode(safeMode);
  }, []);

  useEffect(() => {
    let mounted = true;

    const runInitialAuthCheck = async () => {
      try {
        if (!authBootstrapPromise) {
          authBootstrapPromise = bootstrapAuth();
        }

        const result = await authBootstrapPromise;

        if (!mounted) return;

        setIsLoggedIn(result.loggedIn);
        setUser(result.user);
      } catch (error) {
        console.error("Initial auth check failed:", error);

        if (!mounted) return;

        setIsLoggedIn(false);
        setUser(null);
      } finally {
        if (mounted) {
          setAuthChecked(true);
        }
      }
    };

    runInitialAuthCheck();

    return () => {
      mounted = false;
    };
  }, [bootstrapAuth]);

  useEffect(() => {
    if (!isLoggedIn || !authChecked) return;

    let cancelled = false;
    let requestInFlight = false;
    let lastKeepAliveAt = 0;
    let softFailureCount = 0;

    const KEEP_ALIVE_INTERVAL_MS = 5 * 60 * 1000;
    const EVENT_COOLDOWN_MS = 90 * 1000;
    const MAX_SOFT_FAILURES = 3;

    const clearSession = () => {
      if (cancelled) return;

      authBootstrapPromise = Promise.resolve({
        loggedIn: false,
        user: null,
      });

      setIsLoggedIn(false);
      setUser(null);
    };

    const keepAlive = async (reason = "interval") => {
      if (cancelled) return;
      if (requestInFlight) return;

      const now = Date.now();

      if (reason !== "interval" && now - lastKeepAliveAt < EVENT_COOLDOWN_MS) {
        return;
      }

      requestInFlight = true;
      lastKeepAliveAt = now;

      try {
        const response = await apiFetch(`${API_URL}/auth/user_status`, {
          method: "GET",
          cache: "no-store",
        });

        if (response.status === 401 || response.status === 403) {
          clearSession();
          return;
        }

        if (!response.ok) {
          softFailureCount += 1;

          if (softFailureCount >= MAX_SOFT_FAILURES) {
            console.warn("[KEEP ALIVE] repeated backend failures");
          }

          return;
        }

        const data = await response.json();
        syncCsrfTokenFromResponseData(data);

        const loggedIn =
          data.logged_in === true || data.authenticated === true;

        if (!loggedIn) {
          const refreshedUser = await refreshAuthSession();

          if (refreshedUser?.id) {
            softFailureCount = 0;
            authBootstrapPromise = Promise.resolve({
              loggedIn: true,
              user: refreshedUser,
            });
            setUser(refreshedUser);
          } else {
            softFailureCount += 1;
            if (softFailureCount >= MAX_SOFT_FAILURES) {
              clearSession();
            }
          }
          return;
        }

        softFailureCount = 0;

        if (data.user && !cancelled) {
          const normalizedUser = normalizeUser(data.user);

          authBootstrapPromise = Promise.resolve({
            loggedIn: true,
            user: normalizedUser,
          });

          setUser(normalizedUser);
        }
      } catch (error) {
        softFailureCount += 1;
        console.warn("[KEEP ALIVE] temporary failure:", error);
      } finally {
        requestInFlight = false;
      }
    };

    const intervalId = window.setInterval(() => {
      keepAlive("interval");
    }, KEEP_ALIVE_INTERVAL_MS);

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        keepAlive("visibility");
      }
    };

    const handleOnline = () => {
      keepAlive("online");
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("online", handleOnline);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("online", handleOnline);
    };
  }, [isLoggedIn, authChecked, normalizeUser, refreshAuthSession]);

  const handleLanguageChange = (code) => {
    if (code !== "ar" && code !== "en") return;
    setLang(setAppLanguage(code));
  };

  const getSafePostLoginPath = (userInfo, returnTo) => {
    const nextUserType = normalizeUserType(userInfo?.user_type);
    const nextUserIsAdmin = nextUserType === "admin";

    let nextPath =
      returnTo && returnTo.startsWith("/") && !returnTo.startsWith("//")
        ? returnTo
        : "/dashboard";

    const adminOnlyPaths = ["/admin/users"];

    const userOnlyPaths = [
      "/page-builder",
      "/builder-responses",
      "/builder-data",
      "/my-plan",
      "/settings",
    ];

    const isAdminOnlyPath = adminOnlyPaths.some((path) =>
      nextPath.startsWith(path)
    );

    const isUserOnlyPath = userOnlyPaths.some((path) =>
      nextPath.startsWith(path)
    );

    if (nextUserIsAdmin && isUserOnlyPath) {
      nextPath = "/dashboard";
    }

    if (!nextUserIsAdmin && isAdminOnlyPath) {
      nextPath = "/dashboard";
    }

    return nextPath;
  };

  const handleLoginSuccess = async () => {
    const params = new URLSearchParams(location.search);
    const returnTo = params.get("returnTo");

    try {
      const userInfo = await fetchUserInfo();

      if (!userInfo) {
        throw new Error(appShellContent.errors.postLoginUnauthorized);
      }

      authBootstrapPromise = Promise.resolve({
        loggedIn: true,
        user: userInfo,
      });

      setIsLoggedIn(true);
      setAuthChecked(true);
      setUser(userInfo);

      navigate(getSafePostLoginPath(userInfo, returnTo), { replace: true });
    } catch (error) {
      console.error(appShellContent.errors.postLoginLoad, error);

      authBootstrapPromise = Promise.resolve({
        loggedIn: false,
        user: null,
      });

      setIsLoggedIn(false);
      setAuthChecked(true);
      setUser(null);

      navigate("/login", { replace: true });
    }
  };

  const handleLogout = async () => {
    setDashboardSidebarOpen(false);

    try {
      await apiFetch(`${API_URL}/auth/log_out`, {
        method: "POST",
      });
    } catch (error) {
      console.error("Logout failed:", error);
    } finally {
      authBootstrapPromise = Promise.resolve({
        loggedIn: false,
        user: null,
      });

      setIsLoggedIn(false);
      setAuthChecked(true);
      setUser(null);
      clearCsrfToken();

      applyThemeMode(themeMode);

      navigate("/", { replace: true });
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    }
  };

  const handleUserUpdated = useCallback(
    (nextUser) => {
      const normalizedUser = normalizeUser(nextUser);

      setUser(normalizedUser);

      if (isLoggedIn) {
        authBootstrapPromise = Promise.resolve({
          loggedIn: true,
          user: normalizedUser,
        });
      }
    },
    [isLoggedIn, normalizeUser]
  );

  const goBackToDashboard = () => {
    navigate("/dashboard", { replace: true });
  };

  const renderDashboardSkeleton = (label = t("dashboard:loading.dashboard")) => (
    <div
      className="dashboard-skeleton-layout"
      aria-label={label}
      dir={lang === "ar" ? "rtl" : "ltr"}
    >
      <aside className="dashboard-skeleton-sidebar">
        <div className="skeleton-logo-row">
          <div className="skeleton-circle" />
          <div>
            <div className="skeleton-line skeleton-title" />
            <div className="skeleton-line skeleton-small" />
          </div>
        </div>

        <div className="skeleton-nav">
          {Array.from({ length: 8 }).map((_, index) => (
            <div className="skeleton-sidebar-row" key={index}>
              <div className="skeleton-circle skeleton-sidebar-icon" />
              <div className="skeleton-line skeleton-sidebar-label" />
            </div>
          ))}
        </div>

        <div className="skeleton-sidebar-bottom">
          <div className="skeleton-sidebar-row">
            <div className="skeleton-circle skeleton-sidebar-icon" />
            <div className="skeleton-line skeleton-sidebar-label" />
          </div>

          <div className="skeleton-sidebar-row">
            <div className="skeleton-circle skeleton-sidebar-icon" />
            <div className="skeleton-line skeleton-sidebar-label" />
          </div>

          <div className="skeleton-user-row">
            <div className="skeleton-circle skeleton-user-avatar" />
            <div className="skeleton-user-lines">
              <div className="skeleton-line skeleton-user-badge" />
              <div className="skeleton-line skeleton-user-name" />
              <div className="skeleton-line skeleton-user-email" />
            </div>
          </div>
        </div>
      </aside>

      <section className="dashboard-skeleton-page">
        <div className="dashboard-skeleton-header">
          <div className="skeleton-line skeleton-heading" />
          <div className="skeleton-line skeleton-subheading" />
        </div>

        <div className="dashboard-skeleton-cards">
          <div className="skeleton-card" />
          <div className="skeleton-card" />
          <div className="skeleton-card" />
          <div className="skeleton-card" />
        </div>

        <div className="dashboard-skeleton-panels">
          <div className="skeleton-panel skeleton-panel-large" />
          <div className="skeleton-panel" />
        </div>

        <div className="dashboard-skeleton-panels lower">
          <div className="skeleton-panel" />
          <div className="skeleton-panel" />
        </div>
      </section>
    </div>
  );

  const renderFormBuilderSkeleton = () => (
    <div
      className="forms-loading-shell"
      aria-label="Loading forms"
      dir={lang === "ar" ? "rtl" : "ltr"}
    >
      <aside className="forms-loading-app-rail" aria-hidden="true">
        <span className="forms-loading-avatar forms-loading-shimmer" />
        <div className="forms-loading-rail-stack">
          {Array.from({ length: 6 }).map((_, index) => (
            <span className="forms-loading-rail-icon forms-loading-shimmer" key={index} />
          ))}
        </div>
        <span className="forms-loading-avatar small forms-loading-shimmer" />
      </aside>

      <main className="forms-loading-page">
        <header className="forms-loading-header">
          <span className="forms-loading-line title forms-loading-shimmer" />
          <span className="forms-loading-line subtitle forms-loading-shimmer" />
        </header>

        <div className="forms-loading-workspace">
          <aside className="forms-loading-controls">
            {Array.from({ length: 5 }).map((_, index) => (
              <div className="forms-loading-control-group" key={index}>
                <span className="forms-loading-line label forms-loading-shimmer" />
                <span className="forms-loading-control forms-loading-shimmer" />
              </div>
            ))}
            <div className="forms-loading-actions">
              {Array.from({ length: 4 }).map((_, index) => (
                <span className="forms-loading-button forms-loading-shimmer" key={index} />
              ))}
            </div>
          </aside>

          <section className="forms-loading-document">
            <div className="forms-loading-document-top">
              <span className="forms-loading-line page-title forms-loading-shimmer" />
              <span className="forms-loading-pill forms-loading-shimmer" />
            </div>
            <span className="forms-loading-textarea forms-loading-shimmer" />
            <div className="forms-loading-toolbar">
              {Array.from({ length: 5 }).map((_, index) => (
                <span className="forms-loading-tool forms-loading-shimmer" key={index} />
              ))}
            </div>
            {Array.from({ length: 3 }).map((_, index) => (
              <article className="forms-loading-question" key={index}>
                <span className="forms-loading-dot forms-loading-shimmer" />
                <div className="forms-loading-question-body">
                  <span className="forms-loading-line question-title forms-loading-shimmer" />
                  <span className="forms-loading-control answer forms-loading-shimmer" />
                  <span className="forms-loading-line hint forms-loading-shimmer" />
                </div>
                <span className="forms-loading-type forms-loading-shimmer" />
              </article>
            ))}
          </section>
        </div>
      </main>
    </div>
  );

  const renderFormPreviewSkeleton = () => (
    <main
      className="form-preview-loading-page"
      aria-label={appShellContent.loading.formPreview}
      dir={lang === "ar" ? "rtl" : "ltr"}
    >
      <header className="form-preview-loading-topbar">
        <span className="form-preview-loading-button forms-loading-shimmer" />
        <span className="form-preview-loading-title forms-loading-shimmer" />
      </header>

      <section className="form-preview-loading-shell">
        <div className="form-preview-loading-header">
          <span className="form-preview-loading-line heading forms-loading-shimmer" />
          <span className="form-preview-loading-line copy forms-loading-shimmer" />
        </div>

        {Array.from({ length: 4 }).map((_, index) => (
          <article className="form-preview-loading-question" key={index}>
            <span className="form-preview-loading-line label forms-loading-shimmer" />
            <span className="form-preview-loading-input forms-loading-shimmer" />
            {index < 2 && <span className="form-preview-loading-line help forms-loading-shimmer" />}
          </article>
        ))}

        <footer className="form-preview-loading-actions">
          <span className="form-preview-loading-small-button forms-loading-shimmer" />
          <span className="form-preview-loading-page-pill forms-loading-shimmer" />
          <span className="form-preview-loading-submit forms-loading-shimmer" />
        </footer>
      </section>
    </main>
  );

  const renderDashboardShell = (
    children,
    isPageBuilderShell = false,
    options = {}
  ) => {
    const shellLang = options.lang || lang;
    const isShellRtl = shellLang === "ar";
    const useCompactBuilderSidebar =
      isPageBuilderShell || options.compactSidebar;

    const openMenuLabel = t("common:navigation.openMenu");
    const closeMenuLabel = t("common:navigation.closeMenu");

    const closeDashboardSidebar = () => setDashboardSidebarOpen(false);

    return (
      <div
        className={[
          "admin-dashboard-layout",
          useCompactBuilderSidebar ? "admin-dashboard-layout-builder" : "",
          isShellRtl ? "is-rtl" : "is-ltr",
          dashboardSidebarOpen ? "sidebar-open" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        dir={isShellRtl ? "rtl" : "ltr"}
      >
        <button
          type="button"
          className="dashboard-mobile-menu-button"
          onClick={() => setDashboardSidebarOpen((open) => !open)}
          aria-label={dashboardSidebarOpen ? closeMenuLabel : openMenuLabel}
          aria-expanded={dashboardSidebarOpen}
          aria-controls="dashboard-sidebar"
        >
          {dashboardSidebarOpen ? <X size={22} /> : <Menu size={22} />}
        </button>

        <button
          type="button"
          className="dashboard-sidebar-backdrop"
          onClick={closeDashboardSidebar}
          aria-label={closeMenuLabel}
        />

        <DashboardSidebar
          id="dashboard-sidebar"
          lang={shellLang}
          user={user}
          onLogout={handleLogout}
          onLanguageChange={
            options.hideLanguage ? undefined : handleLanguageChange
          }
          hideLanguage={options.hideLanguage}
          themeMode={themeMode}
          onThemeModeChange={handleThemeModeChange}
          compact={useCompactBuilderSidebar}
          onNavigate={closeDashboardSidebar}
        />

        <main
          className={[
            "admin-dashboard-page",
            isPageBuilderShell ? "page-builder-dashboard-page" : "",
          ]
            .filter(Boolean)
            .join(" ")}
          dir={isShellRtl ? "rtl" : "ltr"}
        >
          {children}
        </main>
      </div>
    );
  };

  const renderRestrictedPage = (message) =>
    renderDashboardShell(
      <RestrictedAccessWindow
        title={appShellContent.restrictedAccess.title}
        message={message}
        actionLabel={appShellContent.restrictedAccess.actionLabel}
        onAction={goBackToDashboard}
      />
    );


  if (isTenantSiteRoute) {
    return (
      <>
        <ScrollToTop />

        <Routes>
          <Route path="/site/:subdomain/*" element={<TenantSiteRuntime />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </>
    );
  }

  if (isDashboardRoute) {
    return (
      <>
        <ScrollToTop />

        <Routes>
          <Route
            path="/dashboard/*"
            element={
              !authChecked ? (
                renderDashboardSkeleton(t("dashboard:loading.dashboard"))
              ) : !isLoggedIn ? (
                <Navigate
                  to={`/login?returnTo=${getCurrentReturnTo()}`}
                  replace
                />
              ) : isAdminUser ? (
                renderDashboardShell(
                  <Dashboard
                    lang={lang}
                    user={user}
                    themeMode={themeMode}
                    onThemeModeChange={handleThemeModeChange}
                  />
                )
              ) : (
                renderDashboardShell(
                  <UserDashboard
                    lang={lang}
                    user={user}
                    themeMode={themeMode}
                    onThemeModeChange={handleThemeModeChange}
                  />
                )
              )
            }
          />

          <Route
            path="/page-builder/form-preview/:formId"
            element={
              !authChecked ? (
                renderFormPreviewSkeleton()
              ) : !isLoggedIn ? (
                <Navigate
                  to={`/login?returnTo=${getCurrentReturnTo()}`}
                  replace
                />
              ) : isRegularUser ? (
                <BuilderFormPreviewPage />
              ) : (
                renderRestrictedPage(
                  appShellContent.restrictedAccess.workspaceOnly
                )
              )
            }
          />

          <Route
            path="/page-builder/preview"
            element={
              !authChecked ? (
                renderDashboardSkeleton(t("dashboard:loading.pageBuilder"))
              ) : !isLoggedIn ? (
                <Navigate
                  to={`/login?returnTo=${getCurrentReturnTo()}`}
                  replace
                />
              ) : isRegularUser ? (
                <TenantSiteRuntime draftPreview />
              ) : (
                renderRestrictedPage(
                  appShellContent.restrictedAccess.workspaceOnly
                )
              )
            }
          />

          <Route
            path="/page-builder/*"
            element={
              !authChecked ? (
                location.pathname.startsWith("/page-builder/forms")
                  ? renderFormBuilderSkeleton()
                  : renderDashboardSkeleton(t("dashboard:loading.pageBuilder"))
              ) : !isLoggedIn ? (
                <Navigate
                  to={`/login?returnTo=${getCurrentReturnTo()}`}
                  replace
                />
              ) : isRegularUser ? (
                renderDashboardShell(
                  <PageBuilder
                    key="page-builder-main"
                    user={user}
                    templateLang={lang}
                    appThemeMode={themeMode}
                    onAppThemeModeChange={handleThemeModeChange}
                  />,
                  true,
                  { lang: "en" }
                )
              ) : (
                renderRestrictedPage(
                  appShellContent.restrictedAccess.workspaceOnly
                )
              )
            }
          />

          <Route
            path="/builder-responses/*"
            element={
              !authChecked ? (
                renderDashboardSkeleton(t("dashboard:loading.submissions"))
              ) : !isLoggedIn ? (
                <Navigate
                  to={`/login?returnTo=${getCurrentReturnTo()}`}
                  replace
                />
              ) : isRegularUser ? (
                renderDashboardShell(
                  <PageBuilder
                    key="builder-responses-page"
                    user={user}
                    initialTab="responses"
                    visibleTabIds={["responses"]}
                    hideWorkspaceTabs={true}
                    lang={lang}
                    templateLang={lang}
                    appThemeMode={themeMode}
                    onAppThemeModeChange={handleThemeModeChange}
                  />,
                  false,
                  { compactSidebar: true }
                )
              ) : (
                renderRestrictedPage(
                  appShellContent.restrictedAccess.workspaceOnly
                )
              )
            }
          />

          <Route
            path="/builder-data/*"
            element={
              !authChecked ? (
                renderDashboardSkeleton(t("dashboard:loading.dataLogs"))
              ) : !isLoggedIn ? (
                <Navigate
                  to={`/login?returnTo=${getCurrentReturnTo()}`}
                  replace
                />
              ) : isRegularUser ? (
                renderDashboardShell(
                  <PageBuilder
                    key="builder-data-page"
                    user={user}
                    initialTab="data"
                    visibleTabIds={["data"]}
                    hideWorkspaceTabs={true}
                    lang={lang}
                    templateLang={lang}
                    appThemeMode={themeMode}
                    onAppThemeModeChange={handleThemeModeChange}
                  />,
                  false,
                  { compactSidebar: true }
                )
              ) : (
                renderRestrictedPage(
                  appShellContent.restrictedAccess.workspaceOnly
                )
              )
            }
          />

          <Route
            path="/my-plan/*"
            element={
              !authChecked ? (
                renderDashboardSkeleton(t("dashboard:loading.myPlan"))
              ) : !isLoggedIn ? (
                <Navigate
                  to={`/login?returnTo=${getCurrentReturnTo()}`}
                  replace
                />
              ) : isRegularUser ? (
                renderDashboardShell(<MyPlanPage lang={lang} />)
              ) : (
                renderRestrictedPage(
                  appShellContent.restrictedAccess.workspaceOnly
                )
              )
            }
          />

          <Route
            path="/admin/users/*"
            element={
              !authChecked ? (
                renderDashboardSkeleton(t("dashboard:loading.userManagement"))
              ) : !isLoggedIn ? (
                <Navigate
                  to={`/login?returnTo=${getCurrentReturnTo()}`}
                  replace
                />
              ) : isAdminUser ? (
                renderDashboardShell(
                  <UserManagementPage lang={lang} currentUser={user} />
                )
              ) : (
                renderRestrictedPage(
                  appShellContent.restrictedAccess.adminOnly
                )
              )
            }
          />

          <Route
            path="/settings/change-password/*"
            element={
              !authChecked ? (
                renderDashboardSkeleton(t("dashboard:loading.passwordSettings"))
              ) : !isLoggedIn ? (
                <Navigate
                  to={`/login?returnTo=${getCurrentReturnTo()}`}
                  replace
                />
              ) : isRegularUser ? (
                renderDashboardShell(<ChangePasswordPage lang={lang} />)
              ) : (
                renderRestrictedPage(
                  appShellContent.restrictedAccess.workspaceOnly
                )
              )
            }
          />

          <Route
            path="/settings/*"
            element={
              !authChecked ? (
                renderDashboardSkeleton(t("dashboard:loading.settings"))
              ) : !isLoggedIn ? (
                <Navigate
                  to={`/login?returnTo=${getCurrentReturnTo()}`}
                  replace
                />
              ) : isRegularUser ? (
                renderDashboardShell(
                  <SettingsPage
                    lang={lang}
                    user={user}
                    onUserUpdated={handleUserUpdated}
                  />
                )
              ) : (
                renderRestrictedPage(
                  appShellContent.restrictedAccess.workspaceOnly
                )
              )
            }
          />

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </>
    );
  }

  return (
    <>
      <ScrollToTop />

      <div className="app-shell" dir={lang === "ar" ? "rtl" : "ltr"}>
        <Header
          lang={lang}
          onLanguageChange={handleLanguageChange}
          isLoggedIn={isLoggedIn}
          onLogout={handleLogout}
          themeMode={themeMode}
          onThemeModeChange={handleThemeModeChange}
        />

        <Routes>
          <Route
            path="/"
            element={
              <main className="app-main">
                <HeroSection key={lang} lang={lang} />
              </main>
            }
          />

          <Route
            path="/demo"
            element={
              <main className="app-main builder-demo-main" dir="ltr" lang="en">
                <PageBuilder
                  key="page-builder-demo"
                  demoMode
                  user={user}
                  lang="en"
                  templateLang={lang}
                  appThemeMode={themeMode}
                  onAppThemeModeChange={handleThemeModeChange}
                />
              </main>
            }
          />

          <Route
            path="/about"
            element={
              <main className="app-main">
                <AboutSection key={lang} lang={lang} />
              </main>
            }
          />

          <Route
            path="/contact"
            element={
              <main className="app-main">
                <ContactPage key={lang} lang={lang} />
              </main>
            }
          />

          <Route
            path="/features"
            element={
              <main className="app-main">
                <FeaturesPage key={lang} lang={lang} />
              </main>
            }
          />

          <Route
            path="/pricing"
            element={
              <main className="app-main">
                <PricingPage key={lang} lang={lang} />
              </main>
            }
          />

          <Route
            path="/team"
            element={
              <main className="app-main">
                <TeamPage key={lang} lang={lang} />
              </main>
            }
          />

          <Route
            path="/reset-password"
            element={
              <main className="app-main">
                <ResetPasswordPage key={lang} lang={lang} />
              </main>
            }
          />

          <Route
            path="/signup"
            element={
              <main className="app-main">
                <SignUpPage key={lang} lang={lang} />
              </main>
            }
          />

          <Route
            path="/forgot-password"
            element={
              <main className="app-main">
                <ForgotPasswordPage key={lang} lang={lang} />
              </main>
            }
          />

          <Route
            path="/login"
            element={
              !authChecked ? (
                <main
                  className="already-signed-page"
                  dir={lang === "ar" ? "rtl" : "ltr"}
                >
                  <section className="already-signed-container">
                    <div
                      className="auth-skeleton-card"
                      aria-label={t("auth:login.checkingSession")}
                    >
                      <div className="auth-skeleton-line auth-skeleton-title" />
                      <div className="auth-skeleton-line auth-skeleton-text" />

                      <div className="auth-skeleton-actions">
                        <div className="auth-skeleton-button primary" />
                        <div className="auth-skeleton-button secondary" />
                      </div>
                    </div>
                  </section>
                </main>
              ) : isLoggedIn ? (
                <main
                  className="already-signed-page"
                  dir={lang === "ar" ? "rtl" : "ltr"}
                >
                  <section className="already-signed-container">
                    <div className="already-signed-card">
                      <h1>{t("auth:login.alreadySignedInTitle")}</h1>

                      <p>{t("auth:login.alreadySignedInBody")}</p>

                      <div className="already-signed-actions">
                        <button
                          type="button"
                          onClick={() =>
                            navigate("/dashboard", { replace: true })
                          }
                        >
                          {t("auth:login.continueToDashboard")}
                        </button>

                        <button type="button" onClick={handleLogout}>
                          {t("common:actions.logout")}
                        </button>
                      </div>
                    </div>
                  </section>
                </main>
              ) : (
                <main className="app-main">
                  <LoginPage
                    key={lang}
                    lang={lang}
                    onLoginSuccess={handleLoginSuccess}
                  />
                </main>
              )
            }
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>

        <Footer lang={lang} />
      </div>
    </>
  );
}
