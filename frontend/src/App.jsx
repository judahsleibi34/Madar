import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import ScrollToTop from "./components/DashboardBuilder/ScrollToTop";
import { appShellContent } from "./content";
import { getCurrentLanguage, setAppLanguage } from "./i18n/language";
import { DashboardLoadingElement, DashboardShell, RestrictedAccessWindow } from "./routes/shared";
import {
  getSafePostLoginPath,
  isDashboardRoutePath,
  isTenantSiteRoutePath,
  normalizeUserType,
} from "./routes/routeUtils";
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


  const dashboardLoadingLabels = {
    dashboard: t("dashboard:loading.dashboard"),
    pageBuilder: t("dashboard:loading.pageBuilder"),
    submissions: t("dashboard:loading.submissions"),
    dataLogs: t("dashboard:loading.dataLogs"),
    myPlan: t("dashboard:loading.myPlan"),
    userManagement: t("dashboard:loading.userManagement"),
    accountAccess: t("dashboard:loading.accountAccess", {
      defaultValue: "Account access",
    }),
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
  }

  return (
    <>
      <ScrollToTop />
      <Suspense fallback={routeFallback}>{routeContent}</Suspense>
    </>
  );
}
