import { lazy, useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import RouteSuspense from "../components/common/RouteSuspense";
import MainLayout from "../components/MainPages/MainLayout";

const loadHomePage = () => import("../components/MainPages/HeroSection");
const loadBasePlansPage = () => import("../components/MainPages/BasePlansPage");

const HomePage = lazy(loadHomePage);
const BasePlansPage = lazy(loadBasePlansPage);
const TeamPage = lazy(() => import("../components/MainPages/TeamPage"));
const AboutSection = lazy(() => import("../components/MainPages/AboutSection"));
const ContactPage = lazy(() => import("../components/MainPages/ContactPage"));
const PrivacyPolicyPage = lazy(() => import("../components/MainPages/PrivacyPolicyPage"));
const PageBuilder = lazy(() => import("../components/PageBuilder"));

const LoginPage = lazy(() => import("../components/AuthPages/LoginPage"));
const SignUpPage = lazy(() => import("../components/AuthPages/SignUpPage"));
const ForgotPasswordPage = lazy(() => import("../components/AuthPages/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("../components/AuthPages/ResetPasswordPage"));

const canPrefetchRoutes = () => {
  if (typeof navigator === "undefined") return true;
  const connection = navigator.connection;
  if (!connection) return true;
  if (connection.saveData) return false;
  return !["slow-2g", "2g"].includes(connection.effectiveType);
};

export default function PublicRoutes({
  authChecked,
  isLoggedIn,
  lang,
  onLanguageChange,
  onLoginSuccess,
  onLogout,
  onThemeModeChange,
  themeMode,
  user,
}) {
  const location = useLocation();
  const isAuthPath =
    location.pathname.startsWith("/login") ||
    location.pathname.startsWith("/signup") ||
    location.pathname.startsWith("/forgot-password") ||
    location.pathname.startsWith("/reset-password");
  const isDemoPath = location.pathname.startsWith("/demo");
  const skeletonVariant = isAuthPath ? "auth" : isDemoPath ? "public-page" : "public-page";

  useEffect(() => {
    if (location.pathname !== "/" || !canPrefetchRoutes()) return undefined;

    const prefetchLikelyPublicRoutes = () => {
      loadBasePlansPage();
    };

    if ("requestIdleCallback" in window) {
      const id = window.requestIdleCallback(prefetchLikelyPublicRoutes, {
        timeout: 2500,
      });
      return () => window.cancelIdleCallback(id);
    }

    const timeoutId = window.setTimeout(prefetchLikelyPublicRoutes, 1600);
    return () => window.clearTimeout(timeoutId);
  }, [location.pathname]);

  return (
    <RouteSuspense
      label={isAuthPath ? "Loading account page" : "Loading page"}
      lang={lang}
      variant={skeletonVariant}
    >
      <Routes>
        <Route
          element={
            <MainLayout
              authChecked={authChecked}
              isLoggedIn={isLoggedIn}
              lang={lang}
              onLanguageChange={onLanguageChange}
              onLogout={onLogout}
              onThemeModeChange={onThemeModeChange}
              themeMode={themeMode}
              user={user}
            />
          }
        >
          <Route index element={<HomePage key={`home-${lang}`} lang={lang} />} />

        <Route
          path="demo"
          element={
            <main className="builder-demo-main">
              <PageBuilder
                key={`builder-demo-${lang}`}
                demoMode
                user={user}
                templateLang={lang}
                appThemeMode={themeMode}
                onAppThemeModeChange={onThemeModeChange}
              />
            </main>
          }
        />

        <Route
          path="pricing"
          element={<BasePlansPage key={`pricing-${lang}`} lang={lang} />}
        />

        <Route
          path="pricing/base-plans"
          element={<BasePlansPage key={`base-plans-${lang}`} lang={lang} />}
        />

        <Route
          path="pricing/custom-plan"
          element={<Navigate to="/pricing" replace />}
        />

        <Route
          path="team"
          element={<TeamPage key={`team-${lang}`} lang={lang} />}
        />

        <Route
          path="about"
          element={<AboutSection key={`about-${lang}`} lang={lang} />}
        />

          <Route
            path="contact"
            element={<ContactPage key={`contact-${lang}`} lang={lang} />}
          />

          <Route
            path="privacy-policy"
            element={<PrivacyPolicyPage key={`privacy-policy-${lang}`} lang={lang} />}
          />

          <Route
            path="login"
            element={
              authChecked && isLoggedIn ? (
                <Navigate to="/dashboard" replace />
              ) : (
                <LoginPage
                  key={`login-${lang}`}
                  lang={lang}
                  onLoginSuccess={onLoginSuccess}
                />
              )
            }
          />

          <Route
            path="signup"
            element={<SignUpPage key={`signup-${lang}`} lang={lang} />}
          />

          <Route
            path="forgot-password"
            element={
              <ForgotPasswordPage key={`forgot-password-${lang}`} lang={lang} />
            }
          />

          <Route
            path="reset-password"
            element={
              <ResetPasswordPage key={`reset-password-${lang}`} lang={lang} />
            }
          />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </RouteSuspense>
  );
}
