import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import MainLayout from "../components/MainPages/MainLayout";

const HomePage = lazy(() => import("../components/MainPages/HeroSection"));
const ProductTourPage = lazy(() => import("../components/MainPages/FeaturesPage"));
const PricingPage = lazy(() => import("../components/MainPages/PricingPage"));
const BasePlansPage = lazy(() => import("../components/MainPages/BasePlansPage"));
const CustomPlanPage = lazy(() => import("../components/MainPages/CustomPlanPage"));
const TeamPage = lazy(() => import("../components/MainPages/TeamPage"));
const AboutSection = lazy(() => import("../components/MainPages/AboutSection"));
const ContactPage = lazy(() => import("../components/MainPages/ContactPage"));

const LoginPage = lazy(() => import("../components/AuthPages/LoginPage"));
const SignUpPage = lazy(() => import("../components/AuthPages/SignUpPage"));
const ForgotPasswordPage = lazy(() => import("../components/AuthPages/ForgotPasswordPage"));
const ResetPasswordPage = lazy(() => import("../components/AuthPages/ResetPasswordPage"));

const publicFallback = (
  <div className="route-loading" role="status" aria-live="polite">
    Loading...
  </div>
);

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
  return (
    <Suspense fallback={publicFallback}>
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
          path="product-tour"
          element={<ProductTourPage key={`product-tour-${lang}`} lang={lang} />}
        />

        <Route
          path="pricing"
          element={<PricingPage key={`pricing-${lang}`} lang={lang} />}
        />

        <Route
          path="pricing/base-plans"
          element={<BasePlansPage key={`base-plans-${lang}`} lang={lang} />}
        />

        <Route
          path="pricing/custom-plan"
          element={<CustomPlanPage key={`custom-plan-${lang}`} lang={lang} />}
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
        </Route>

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

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
