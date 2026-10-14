import { lazy, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";

import PageSkeleton from "../components/common/PageSkeleton";
import RouteSuspense from "../components/common/RouteSuspense";
import { ensureTranslations, hasTranslations } from "../i18n";
import { TRANSLATION_LANGUAGES, TRANSLATION_NAMESPACES } from "../i18n/translationBundles";
import {
  getLoadedTenantRouteModule,
  getPendingTenantRouteModule,
  loadTenantRouteModule,
  ROUTE_TRANSLATION_NAMESPACES,
} from "../tenantRuntimePreload";
import { buildCanonicalTenantUrl, getBrandedMadarSubdomain } from "../utils/hostedAddress";

const ROUTE_LOADING_LABEL = "Loading site";
const ROUTE_LOADING_VARIANT = "tenant-runtime";

// A route is ready once its code and the translation namespaces it renders
// are both present; neither is ever rendered without the other.
const withTranslations = (load, ensure) => () =>
  Promise.all([load(), ensure()]).then(([module]) => module);

// Route components share the entry's preload. While that preload is still in
// flight the route shows the same skeleton the Suspense fallback renders, but
// as plain state rather than a suspended render, so React's Suspense reveal
// throttle does not hold the route back once its code has arrived. Without a
// preload the route suspends exactly like a plain lazy() route.
const preloadedRoute = (kind) => {
  const namespaces = ROUTE_TRANSLATION_NAMESPACES[kind];
  const LazyRoute = lazy(withTranslations(() => loadTenantRouteModule(kind), () => ensureTranslations(namespaces)));
  return function PreloadedRoute(props) {
    const [routeModule, setRouteModule] = useState(() =>
      (hasTranslations(namespaces) ? getLoadedTenantRouteModule(kind) : null)
    );
    const [preloadFailed, setPreloadFailed] = useState(false);
    const pending = routeModule || preloadFailed ? null : getPendingTenantRouteModule(kind);

    useEffect(() => {
      if (!pending) return undefined;
      let active = true;
      Promise.all([pending, ensureTranslations(namespaces)]).then(
        ([loaded]) => { if (active) setRouteModule(loaded); },
        () => { if (active) setPreloadFailed(true); },
      );
      return () => { active = false; };
    }, [pending]);

    if (routeModule) {
      const RouteComponent = routeModule.default;
      return <RouteComponent {...props} />;
    }
    if (pending) return <PageSkeleton label={ROUTE_LOADING_LABEL} variant={ROUTE_LOADING_VARIANT} />;
    return <LazyRoute {...props} />;
  };
};

const TenantSiteRuntime = preloadedRoute("site");
const EcommerceStorefront = preloadedRoute("store");

// Academy pages render every namespace and switch language in place, so they
// keep every namespace in both languages, as all tenant pages once did.
const ensureAllTranslations = () =>
  Promise.all(TRANSLATION_LANGUAGES.map((language) => ensureTranslations(TRANSLATION_NAMESPACES, language)));

const ELearningAcademy = lazy(withTranslations(() => import("../components/ELearning/ELearningAcademy"), ensureAllTranslations));
const HostedAcademyLearning = lazy(withTranslations(
  () => import("../components/ELearning/ELearningAcademy").then(m => ({ default: m.HostedAcademyLearning })),
  ensureAllTranslations,
));

function HostedStorefront({ subdomain }) {
  if (!subdomain) return <Navigate to="/" replace />;
  return <EcommerceStorefront subdomain={subdomain} />;
}

function AdminStorePreview() {
  const { subdomain } = useParams();
  if (!buildCanonicalTenantUrl(subdomain, "/shop")) return <Navigate to="/" replace />;
  return <EcommerceStorefront subdomain={subdomain} previewBasePath={`/ecommerce-preview/${encodeURIComponent(subdomain)}`} />;
}

function LegacyTenantRedirect({ prefix }) {
  const params = useParams();
  const location = useLocation();
  const [failedIdentifier, setFailedIdentifier] = useState("");
  const legacyIdentifier = String(params.subdomain || "").trim().toLowerCase();
  const wildcard = String(params["*"] || "").replace(/^\/+/, "");
  const formId = String(params.formId || "");

  useEffect(() => {
    let cancelled = false;
    import("../components/PageBuilder/services/PageBuilder.publicApi")
      .then(({ fetchPublicSiteBootstrap }) => fetchPublicSiteBootstrap(legacyIdentifier))
      .then((payload) => {
        if (cancelled) return;
        const canonicalTenant = String(payload?.site?.subdomain || "").trim().toLowerCase();
        const formSuffix = formId ? `/forms/${encodeURIComponent(formId)}` : "";
        const tail = formSuffix || `${prefix}${wildcard ? `/${wildcard}` : ""}` || "/";
        const target = buildCanonicalTenantUrl(
          canonicalTenant,
          `${tail}${location.search}${location.hash}`
        );
        if (!target) throw new Error("Invalid canonical tenant address");
        window.location.replace(target);
      })
      .catch(() => {
        if (!cancelled) setFailedIdentifier(legacyIdentifier);
      });
    return () => { cancelled = true; };
  }, [formId, legacyIdentifier, location.hash, location.search, prefix, wildcard]);

  return failedIdentifier === legacyIdentifier ? <Navigate to="/" replace /> : null;
}

export default function TenantSiteRoutes() {
  const location = useLocation();
  const hostedTenant = getBrandedMadarSubdomain(window.location.hostname);
  const siteMatch = location.pathname.match(/^\/site\/([^/]+)(?:\/|$)/i);
  const currentSubdomain = siteMatch ? decodeURIComponent(siteMatch[1]) : "";
  const isShopRoute = /^\/site\/[^/]+\/shop(?:\/|$)/i.test(location.pathname);

  useEffect(() => {
    if (!currentSubdomain || isShopRoute) return undefined;
    const preload = () => {
      import("../components/EcommerceStore/EcommerceStorefront");
      import("../services/ecommerceApi")
        .then(({ preloadPublicEcommerceCatalog }) => preloadPublicEcommerceCatalog(currentSubdomain))
        .catch(() => {});
    };
    if (typeof window.requestIdleCallback === "function") {
      const idleId = window.requestIdleCallback(preload, { timeout: 1500 });
      return () => window.cancelIdleCallback?.(idleId);
    }
    const timeoutId = window.setTimeout(preload, 250);
    return () => window.clearTimeout(timeoutId);
  }, [currentSubdomain, isShopRoute]);

  return (
    <RouteSuspense label={ROUTE_LOADING_LABEL} variant={ROUTE_LOADING_VARIANT} delay={0}>
      <Routes>
        {hostedTenant ? (
          <>
            <Route path="/academy/*" element={<ELearningAcademy subdomain={hostedTenant} />} />
            <Route path="/my-learning/*" element={<HostedAcademyLearning subdomain={hostedTenant} />} />
            <Route path="/shop/*" element={<HostedStorefront subdomain={hostedTenant} />} />
            <Route path="/forms/:formId" element={<TenantSiteRuntime siteIdentifier={hostedTenant} />} />
            <Route path="/*" element={<TenantSiteRuntime siteIdentifier={hostedTenant} />} />
          </>
        ) : (
          <>
            <Route path="/academy/:subdomain/*" element={<ELearningAcademy />} />
            <Route path="/forms/:subdomain/:formId" element={<LegacyTenantRedirect prefix="" />} />
            <Route path="/store/:subdomain/*" element={<LegacyTenantRedirect prefix="/shop" />} />
            <Route path="/ecommerce-preview/:subdomain/*" element={<AdminStorePreview />} />
            <Route path="/site/:subdomain/*" element={<LegacyTenantRedirect prefix="" />} />
            <Route path="/shop/*" element={<Navigate to="/" replace />} />
          </>
        )}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </RouteSuspense>
  );
}
