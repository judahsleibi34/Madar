import { useCallback, useEffect, useState } from "react";
import {
  Routes,
  Route,
  useNavigate,
  Navigate,
  useLocation,
} from "react-router-dom";

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
import MyPlanPage from "./components/MainPages/MyPlanPage";

import PageBuilder from "./components/PageBuilder";
import TenantSiteRuntime from "./components/PageBuilder/TenantSiteRuntime";

import { applyThemeMode, readStoredThemeMode } from "./utils/themeMode";

const API_URL = import.meta.env.VITE_API_URL || "/api";
const LANG_STORAGE_KEY = "madar-lang";

let authBootstrapPromise = null;

export default function App() {
  const [lang, setLang] = useState(() => {
    const savedLang = localStorage.getItem(LANG_STORAGE_KEY);
    return savedLang === "ar" || savedLang === "en" ? savedLang : "en";
  });

  const [themeMode, setThemeMode] = useState(readStoredThemeMode);

  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const [user, setUser] = useState(null);

  const navigate = useNavigate();
  const location = useLocation();

  const isTenantSiteRoute = location.pathname.startsWith("/site/");

  const isDashboardRoute =
    location.pathname.startsWith("/dashboard") ||
    location.pathname.startsWith("/page-builder") ||
    location.pathname.startsWith("/builder-responses") ||
    location.pathname.startsWith("/builder-data") ||
    location.pathname.startsWith("/my-plan") ||
    location.pathname.startsWith("/admin/users") ||
    location.pathname.startsWith("/settings");

  const normalizeUser = useCallback((userInfo) => {
    const firstName = userInfo?.first_name || "";
    const lastName = userInfo?.last_name || "";
    const fullName =
      userInfo?.name ||
      `${firstName} ${lastName}`.trim() ||
      userInfo?.username ||
      "User";

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
      payment_status: userInfo?.payment_status || "",
      user_type: userInfo?.user_type || "user",
      created_at: userInfo?.created_at || "",
      updated_at: userInfo?.updated_at || "",
    };
  }, []);

  const fetchUserInfo = useCallback(async () => {
    const response = await fetch(`${API_URL}/user/info`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    });

    if (response.status === 401 || response.status === 403) {
      return null;
    }

    if (!response.ok) {
      const error = new Error("Could not fetch user info");
      error.status = response.status;
      throw error;
    }

    const data = await response.json();
    return normalizeUser(data.user || data);
  }, [normalizeUser]);

  const bootstrapAuth = useCallback(async () => {
    try {
      const statusResponse = await fetch(`${API_URL}/auth/user_status`, {
        method: "GET",
        credentials: "include",
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

      const loggedIn =
        statusData.logged_in === true || statusData.authenticated === true;

      if (!loggedIn) {
        return {
          loggedIn: false,
          user: null,
        };
      }

      const userInfo = await fetchUserInfo();

      if (!userInfo) {
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
  }, [fetchUserInfo]);

  useEffect(() => {
    localStorage.setItem(LANG_STORAGE_KEY, lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  useEffect(() => {
    applyThemeMode(themeMode);
  }, [themeMode]);

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
        const response = await fetch(`${API_URL}/auth/user_status`, {
          method: "GET",
          credentials: "include",
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

        const loggedIn =
          data.logged_in === true || data.authenticated === true;

        if (!loggedIn) {
          clearSession();
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
  }, [isLoggedIn, authChecked, normalizeUser]);

  const handleLanguageChange = (code) => {
    if (code !== "ar" && code !== "en") return;
    setLang(code);
  };

  const handleLoginSuccess = async () => {
    const params = new URLSearchParams(location.search);
    const returnTo = params.get("returnTo");

    try {
      const userInfo = await fetchUserInfo();

      if (!userInfo) {
        throw new Error("Login succeeded but user info was unauthorized");
      }

      authBootstrapPromise = Promise.resolve({
        loggedIn: true,
        user: userInfo,
      });

      setIsLoggedIn(true);
      setAuthChecked(true);
      setUser(userInfo);

      navigate(returnTo || "/dashboard", { replace: true });
    } catch (error) {
      console.error("Could not load user info after login:", error);

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
    try {
      await fetch(`${API_URL}/auth/log_out`, {
        method: "POST",
        credentials: "include",
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

  const renderDashboardSkeleton = (label = "Loading dashboard") => (
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
          <div className="skeleton-line skeleton-nav-item" />
          <div className="skeleton-line skeleton-nav-item" />
          <div className="skeleton-line skeleton-nav-item" />
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

  const renderDashboardShell = (
    children,
    isPageBuilderShell = false,
    options = {}
  ) => {
    const shellLang = options.lang || lang;

    return (
      <div
        className={`admin-dashboard-layout ${
          isPageBuilderShell ? "admin-dashboard-layout-builder " : ""
        }${shellLang === "ar" ? "is-rtl" : "is-ltr"}`}
        dir={shellLang === "ar" ? "rtl" : "ltr"}
      >
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
        />

        <main
          className={`admin-dashboard-page${
            isPageBuilderShell ? " page-builder-dashboard-page" : ""
          }`}
          dir={shellLang === "ar" ? "rtl" : "ltr"}
        >
          {children}
        </main>
      </div>
    );
  };

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
            path="/dashboard"
            element={
              !authChecked ? (
                renderDashboardSkeleton("Loading dashboard")
              ) : isLoggedIn ? (
                <Dashboard
                  lang={lang}
                  onLogout={handleLogout}
                  user={user}
                  onLanguageChange={handleLanguageChange}
                  themeMode={themeMode}
                  onThemeModeChange={handleThemeModeChange}
                />
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          <Route
            path="/page-builder"
            element={
              !authChecked ? (
                renderDashboardSkeleton("Loading page builder")
              ) : isLoggedIn ? (
                renderDashboardShell(
                  <PageBuilder
                    key="page-builder-main"
                    templateLang={lang}
                    appThemeMode={themeMode}
                    onAppThemeModeChange={handleThemeModeChange}
                  />,
                  true,
                  { lang: "en", hideLanguage: true }
                )
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          <Route
            path="/builder-responses"
            element={
              !authChecked ? (
                renderDashboardSkeleton("Loading submissions")
              ) : isLoggedIn ? (
                renderDashboardShell(
                  <PageBuilder
                    key="builder-responses-page"
                    initialTab="responses"
                    visibleTabIds={["responses"]}
                    hideWorkspaceTabs={true}
                    lang={lang}
                    templateLang={lang}
                    appThemeMode={themeMode}
                    onAppThemeModeChange={handleThemeModeChange}
                  />,
                  false
                )
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          <Route
            path="/builder-data"
            element={
              !authChecked ? (
                renderDashboardSkeleton("Loading data logs")
              ) : isLoggedIn ? (
                renderDashboardShell(
                  <PageBuilder
                    key="builder-data-page"
                    initialTab="data"
                    visibleTabIds={["data"]}
                    hideWorkspaceTabs={true}
                    lang={lang}
                    templateLang={lang}
                    appThemeMode={themeMode}
                    onAppThemeModeChange={handleThemeModeChange}
                  />,
                  false
                )
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          <Route
            path="/my-plan"
            element={
              !authChecked ? (
                renderDashboardSkeleton("Loading my plan")
              ) : isLoggedIn ? (
                renderDashboardShell(<MyPlanPage lang={lang} />)
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          <Route
            path="/admin/users"
            element={
              !authChecked ? (
                renderDashboardSkeleton("Loading user management")
              ) : isLoggedIn ? (
                renderDashboardShell(
                  <UserManagementPage lang={lang} currentUser={user} />
                )
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          <Route
            path="/settings"
            element={
              !authChecked ? (
                renderDashboardSkeleton("Loading settings")
              ) : isLoggedIn ? (
                renderDashboardShell(
                  <SettingsPage
                    lang={lang}
                    user={user}
                    onUserUpdated={handleUserUpdated}
                  />
                )
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          <Route
            path="/settings/change-password"
            element={
              !authChecked ? (
                renderDashboardSkeleton("Loading password settings")
              ) : isLoggedIn ? (
                renderDashboardShell(<ChangePasswordPage lang={lang} />)
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </>
    );
  }

  return (
    <>
      <ScrollToTop />

      <div className="app-shell">
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
                      aria-label="Checking your session"
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
                      <h1>
                        {lang === "ar"
                          ? "أنت مسجل الدخول بالفعل"
                          : "You are already signed in"}
                      </h1>

                      <p>
                        {lang === "ar"
                          ? "يمكنك المتابعة إلى لوحة التحكم أو تسجيل الخروج واستخدام حساب آخر."
                          : "You can continue to your dashboard or log out and use another account."}
                      </p>

                      <div className="already-signed-actions">
                        <button
                          type="button"
                          onClick={() => navigate("/dashboard")}
                        >
                          {lang === "ar"
                            ? "المتابعة إلى لوحة التحكم"
                            : "Continue to dashboard"}
                        </button>

                        <button type="button" onClick={handleLogout}>
                          {lang === "ar" ? "تسجيل الخروج" : "Log out"}
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
