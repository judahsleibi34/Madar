import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import TeamPage from "./components/MainPages/TeamPage";
import Header from "./components/MainPages/Header";
import HeroSection from "./components/MainPages/HeroSection";
import AboutSection from "./components/MainPages/AboutSection";
import ContactPage from "./components/MainPages/ContactPage";
import FeaturesPage from "./components/MainPages/FeaturesPage";
import PricingPage from "./components/MainPages/PricingPage";
import PrivacyPolicyPage from "./components/MainPages/PrivacyPolicyPage";
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
import SecurityMfaPage from "./components/DashboardBuilder/SecurityMfaPage";
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
import { applyThemeMode, readStoredThemeMode } from "./utils/themeMode";

import "./components/DashboardBuilder/DashboardShellFix.css";

const API_URL = import.meta.env.VITE_API_URL || "/api";

const AdminRoutes = lazy(() => import("./routes/AdminRoutes"));
const PublicRoutes = lazy(() => import("./routes/PublicRoutes"));
const TenantSiteRoutes = lazy(() => import("./routes/TenantSiteRoutes"));
const UserWorkspaceRoutes = lazy(() => import("./routes/UserWorkspaceRoutes"));

let authBootstrapPromise = null;

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
  const isTenantSiteRoute = isTenantSiteRoutePath(location.pathname);
  const isDashboardRoute = isDashboardRoutePath(location.pathname);

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

    const loggedIn = data.logged_in === true || data.authenticated === true;

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

  const shellProps = {
    closeMenuLabel: t("common:navigation.closeMenu"),
    lang,
    onLanguageChange: handleLanguageChange,
    onLogout: handleLogout,
    onNavigate: () => setDashboardSidebarOpen(false),
    onSidebarToggle: () => setDashboardSidebarOpen((open) => !open),
    onThemeModeChange: handleThemeModeChange,
    open: dashboardSidebarOpen,
    openMenuLabel: t("common:navigation.openMenu"),
    themeMode,
    user,
  };

  const dashboardLoadingLabels = {
    dashboard: t("dashboard:loading.dashboard"),
    pageBuilder: t("dashboard:loading.pageBuilder"),
    submissions: t("dashboard:loading.submissions"),
    dataLogs: t("dashboard:loading.dataLogs"),
    myPlan: t("dashboard:loading.myPlan"),
    userManagement: t("dashboard:loading.userManagement"),
    passwordSettings: t("dashboard:loading.passwordSettings"),
    settings: t("dashboard:loading.settings"),
  };

  const routeFallback = isDashboardRoute ? (
    <DashboardLoadingElement
      pathname={location.pathname}
      labels={dashboardLoadingLabels}
      lang={lang}
    />
  ) : (
    <div className="route-loading" role="status" aria-live="polite">
      Loading...
    </div>
  );

  let routeContent;

  if (isTenantSiteRoute) {
    routeContent = <TenantSiteRoutes />;
  } else if (isDashboardRoute) {
    if (!authChecked) {
      routeContent = (
        <DashboardLoadingElement
          pathname={location.pathname}
          labels={dashboardLoadingLabels}
          lang={lang}
        />
      );
    } else if (!isLoggedIn) {
      routeContent = (
        <Navigate to={`/login?returnTo=${getCurrentReturnTo()}`} replace />
      );
    } else if (isAdminUser) {
      routeContent = (
        <AdminRoutes
          lang={lang}
          onGoToDashboard={() => navigate("/dashboard", { replace: true })}
          shellProps={shellProps}
          themeMode={themeMode}
          user={user}
        />
      );
    } else {
      routeContent = (
        <UserWorkspaceRoutes
          lang={lang}
          onGoToDashboard={() => navigate("/dashboard", { replace: true })}
          onUserUpdated={handleUserUpdated}
          shellProps={shellProps}
          themeMode={themeMode}
          user={user}
        />
      );
    }
  } else {
    routeContent = (
      <PublicRoutes
        authChecked={authChecked}
        isLoggedIn={isLoggedIn}
        lang={lang}
        onLanguageChange={handleLanguageChange}
        onLoginSuccess={handleLoginSuccess}
        onLogout={handleLogout}
        onThemeModeChange={handleThemeModeChange}
        themeMode={themeMode}
        user={user}
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
            path="/settings/security/*"
            element={
              !authChecked ? (
                renderDashboardSkeleton(t("dashboard:loading.securitySettings"))
              ) : !isLoggedIn ? (
                <Navigate
                  to={`/login?returnTo=${getCurrentReturnTo()}`}
                  replace
                />
              ) : (
                renderDashboardShell(<SecurityMfaPage lang={lang} />)
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
            path="/privacy-policy"
            element={
              <main className="app-main">
                <PrivacyPolicyPage key={lang} lang={lang} />
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
