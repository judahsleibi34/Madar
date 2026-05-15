import { useEffect, useState } from "react";
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
import PricingPage from "./components/PricingPage";
import ResetPasswordPage from "./components/ResetPasswordPage";
import Dashboard from "./components/Dashboard";
import Footer from "./components/Footer";
import PageBuilder from "./components/PageBuilder";
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

  const hideAppChrome =
    location.pathname.startsWith("/dashboard") ||
    location.pathname.startsWith("/page-builder");

  const normalizeUser = (userInfo) => {
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
      avatar: userInfo?.avatar || userInfo?.avatar_url || "",
    };
  };

  const fetchUserInfo = async () => {
    const response = await fetch(`${API_URL}/user_info`, {
      method: "POST",
      credentials: "include",
    });

    if (!response.ok) {
      throw new Error("Could not fetch user info");
    }

    const data = await response.json();
    return normalizeUser(data.user);
  };

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
  }, []);

  const handleLanguageChange = (code) => {
    if (code !== "ar" && code !== "en") return;
    setLang(code);
  };

  const handleLoginSuccess = async () => {
    try {
      const userInfo = await fetchUserInfo();

      setIsLoggedIn(true);
      setUser(userInfo);
      navigate("/dashboard", { replace: true });
    } catch (error) {
      console.error("Could not load user info after login:", error);

      setIsLoggedIn(true);
      setUser(null);
      navigate("/dashboard", { replace: true });
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

      window.scrollTo({
        top: 0,
        left: 0,
        behavior: "auto",
      });
    }
  };

  const renderDashboardSkeleton = (label = "Loading dashboard") => {
    return (
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
  };

  return (
    <>
      <ScrollToTop />

      <div className="app-shell">
        {!hideAppChrome && (
          <Header
            lang={lang}
            onLanguageChange={handleLanguageChange}
            isLoggedIn={isLoggedIn}
            onLogout={handleLogout}
          />
        )}

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

          <Route
            path="/dashboard"
            element={
              !authChecked ? (
                renderDashboardSkeleton("Loading dashboard")
              ) : isLoggedIn ? (
                <Dashboard lang={lang} onLogout={handleLogout} user={user} />
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
                <div
                  className="admin-dashboard-layout"
                  dir={lang === "ar" ? "rtl" : "ltr"}
                >
                  <DashboardSidebar
                    lang={lang}
                    user={user}
                    onLogout={handleLogout}
                  />

                  <main className="admin-dashboard-page page-builder-dashboard-page">
                    <PageBuilder />
                  </main>
                </div>
              ) : (
                <Navigate to="/login" replace />
              )
            }
          />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>

        {!hideAppChrome && <Footer lang={lang} />}
      </div>
    </>
  );
}