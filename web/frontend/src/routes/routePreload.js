import { useEffect } from "react";

const routes = [
  [/^\/ecommerce\/products\/(?:new|[^/]+\/edit)(?:\/|$)/, () => import("../components/DashboardBuilder/EcommerceProductEditorPage")],
  [/^\/ecommerce\/delivery(?:\/|$)/, () => import("../components/DashboardBuilder/EcommerceDeliveryPage")],
  [/^\/ecommerce\/orders(?:\/|$)/, () => import("../components/DashboardBuilder/EcommerceOrdersPage")],
  [/^\/ecommerce\/loyalty(?:\/|$)/, () => import("../components/DashboardBuilder/EcommerceLoyaltyPage")],
  [/^\/ecommerce\/theme(?:\/|$)/, () => import("../components/DashboardBuilder/EcommerceThemePage")],
  [/^\/ecommerce\/store(?:\/|$)/, () => import("../components/DashboardBuilder/EcommerceStorePage")],
  [/^\/(?:ecommerce\/)?cv-rerank(?:\/|$)/, () => import("../components/DashboardBuilder/CvRerankPage")],
  [/^\/ecommerce(?:\/|$)/, () => import("../components/DashboardBuilder/EcommercePage")],
  [/^\/dashboard(?:\/|$)/, () => Promise.all([import("../components/DashboardBuilder/UserDashboard"), import("../components/DashboardBuilder/Dashboard")])],
  [/^\/demo(?:\/|$)/, () => import("../components/PageBuilder")],
  [/^\/settings\/change-password(?:\/|$)/, () => import("../components/DashboardBuilder/ChangePasswordPage")],
  [/^\/settings(?:\/|$)/, () => import("../components/DashboardBuilder/SettingsPage")],
  [/^\/notifications(?:\/|$)/, () => import("../components/DashboardBuilder/NotificationsPage")],
  [/^\/my-plan(?:\/|$)/, () => import("../components/DashboardBuilder/MyPlanPage")],
  [/^\/(?:calendar|agenda)(?:\/|$)/, () => import("../components/DashboardBuilder/ReservationCalendarPage")],
  [/^\/archive(?:\/|$)/, () => import("../components/DashboardBuilder/ArchivePage")],
  [/^\/(?:page-builder|builder-data|builder-responses)(?:\/|$)/, () => import("../components/PageBuilder")],
  [/^\/admin\/users(?:\/|$)/, () => import("../components/DashboardBuilder/UserManagementPage")],
  [/^\/admin\/account-access(?:\/|$)/, () => import("../components/DashboardBuilder/AdminAccountAccessPage")],
  [/^\/(?:site\/[^/]+\/)?shop(?:\/|$)/, () => import("../components/EcommerceStore/EcommerceStorefront")],
  [/^\/site(?:\/|$)/, () => import("../components/PageBuilder/runtime/TenantSiteRuntime")],
  [/^\/login(?:\/|$)/, () => import("../components/AuthPages/LoginPage")],
  [/^\/signup(?:\/|$)/, () => import("../components/AuthPages/SignUpPage")],
  [/^\/forgot-password(?:\/|$)/, () => import("../components/AuthPages/ForgotPasswordPage")],
  [/^\/reset-password(?:\/|$)/, () => import("../components/AuthPages/ResetPasswordPage")],
  [/^\/verify-email(?:\/|$)/, () => import("../components/AuthPages/EmailVerificationPage")],
  [/^\/pricing(?:\/|$)/, () => import("../components/MainPages/BasePlansPage")],
  [/^\/(?:about|team)(?:\/|$)/, () => Promise.all([import("../components/MainPages/AboutSection"), import("../components/MainPages/TeamPage")])],
  [/^\/contact(?:\/|$)/, () => import("../components/MainPages/ContactPage")],
  [/^\/(?:privacy-policy|terms-and-conditions)(?:\/|$)/, () => Promise.all([import("../components/MainPages/PrivacyPolicyPage"), import("../components/MainPages/TermsAndConditionsPage")])],
  [/^\/$/, () => import("../components/MainPages/HeroSection")],
];
const pending = new Map();

export function getRoutePreloader(pathname) {
  return routes.find(([pattern]) => pattern.test(pathname))?.[1];
}

export function preloadRoute(href, { origin = window.location.origin, connection = navigator.connection } = {}) {
  if (connection?.saveData || ["slow-2g", "2g"].includes(connection?.effectiveType)) return;
  let url;
  try { url = new URL(href, origin); } catch { return; }
  if (url.origin !== origin) return;
  const loader = getRoutePreloader(url.pathname);
  if (!loader || pending.has(loader)) return;
  const request = Promise.resolve().then(loader).catch(() => { pending.delete(loader); });
  pending.set(loader, request);
  return request;
}

export function useRoutePreloading() {
  useEffect(() => {
    const onIntent = (event) => {
      const target = event.target?.closest?.("a[href], [data-route-path]");
      if (!target || target.hasAttribute("download") || target.getAttribute("target") === "_blank") return;
      preloadRoute(target.dataset.routePath || target.getAttribute("href"));
    };
    document.addEventListener("pointerover", onIntent);
    document.addEventListener("focusin", onIntent);
    document.addEventListener("touchstart", onIntent, { passive:true });
    return () => {
      document.removeEventListener("pointerover", onIntent);
      document.removeEventListener("focusin", onIntent);
      document.removeEventListener("touchstart", onIntent);
    };
  }, []);
}
