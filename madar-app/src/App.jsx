import { useCallback, useEffect, useState } from "react";
import {
  Routes,
  Route,
  useNavigate,
  Navigate,
  useLocation,
} from "react-router-dom";

import TeamPage from "./components/TeamPage";
import Header from "./components/Header";
import HeroSection from "./components/HeroSection";
import AboutSection from "./components/AboutSection";
import ContactPage from "./components/ContactPage";
import ScrollToTop from "./components/ScrollToTop";

import LoginPage from "./components/LoginPage";
import SignUpPage from "./components/SignUpPage";
import ForgotPasswordPage from "./components/ForgotPasswordPage";
import FeaturesPage from "./components/FeaturesPage";
import PricingPage from "./components/PricingPage";
import ResetPasswordPage from "./components/ResetPasswordPage";
import Dashboard from "./components/Dashboard";
import SettingsPage from "./components/SettingsPage";
import Footer from "./components/Footer";
import PageBuilder from "./components/PageBuilder";
import TenantSiteRuntime from "./components/PageBuilder/TenantSiteRuntime";
import DashboardSidebar from "./components/DashboardSidebar";

const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
const LANG_STORAGE_KEY = "madar-lang";

export default function App() {
  const [lang, setLang] = useState(() => {
    const savedLang = localStorage.getItem(LANG_STORAGE_KEY);
    return savedLang === "ar" || savedLang === "en" ? savedLang : "en";
  });

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
      first_name: firstName,
      last_name: lastName,
      name: fullName,
      email: userInfo?.email || "",
      phone: userInfo?.phone || "",
      avatar: userInfo?.avatar || userInfo?.avatar_url || "",
      created_at: userInfo?.created_at || "",
      updated_at: userInfo?.updated_at || "",
    };
  }, []);

  const fetchUserInfo = useCallback(async () => {
    const response = await fetch(`${API_URL}/user_info`, {
      method: "POST",
      credentials: "include",
    });

    if (!response.ok) throw new Error("Could not fetch user info");

    const data = await response.json();
    return normalizeUser(data.user);
  }, [normalizeUser]);

  useEffect(() => {
    localStorage.setItem(LANG_STORAGE_KEY, lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
  }, [lang]);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const statusResponse = await fetch(`${API_URL}/user_status`, {
          method: "GET",
          credentials: "include",
        });

        if (!statusResponse.ok) {
          setIsLoggedIn(false);
          setUser(null);
          return;
        }

        const statusData = await statusResponse.json();

        if (statusData.logged_in !== true) {
          setIsLoggedIn(false);
          setUser(null);
          return;
        }

        const userInfo = await fetchUserInfo();

        setIsLoggedIn(true);
        setUser(userInfo);
      } catch (error) {
        console.error("Auth check failed:", error);
        setIsLoggedIn(false);
        setUser(null);
      } finally {
        setAuthChecked(true);
      }
    };

    checkAuth();
  }, [fetchUserInfo]);

  const handleLanguageChange = (code) => {
    if (code !== "ar" && code !== "en") return;
    setLang(code);
  };

  const handleLoginSuccess = async () => {
    const params = new URLSearchParams(location.search);
    const returnTo = params.get("returnTo");

    try {
      const userInfo = await fetchUserInfo();

      setIsLoggedIn(true);
      setUser(userInfo);

      navigate(returnTo || "/dashboard", { replace: true });
    } catch (error) {
      console.error("Could not load user info after login:", error);

      setIsLoggedIn(true);
      setUser(null);

      navigate(returnTo || "/dashboard", { replace: true });
    }
  };

  const handleLogout = async () => {
    try {
      await fetch(`${API_URL}/log_out`, {
        method: "POST",
        credentials: "include",
      });
    } catch (error) {
      console.error("Logout failed:", error);
    } finally {
      setIsLoggedIn(false);
      setUser(null);
      navigate("/", { replace: true });
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    }
  };

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

  const renderDashboardShell = (children, isPageBuilderShell = false, options = {}) => {
    const shellLang = options.lang || lang;

    return (
    <div
      className="admin-dashboard-layout"
      dir={shellLang === "ar" ? "rtl" : "ltr"}
    >
      <DashboardSidebar
        lang={shellLang}
        user={user}
        onLogout={handleLogout}
        onLanguageChange={options.hideLanguage ? undefined : handleLanguageChange}
        hideLanguage={options.hideLanguage}
      />

      <main className={`admin-dashboard-page${isPageBuilderShell ? " page-builder-dashboard-page" : ""}`}>
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
                  <PageBuilder key="page-builder-main" templateLang={lang} />,
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
                  />,
                  true
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
                  />,
                  true
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
                    onUserUpdated={(nextUser) => setUser(normalizeUser(nextUser))}
                  />
                )
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
                <PageBuilder key="page-builder-demo" demoMode lang="en" templateLang={lang} />
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
              authChecked && isLoggedIn ? (
                <Navigate to="/dashboard" replace />
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
