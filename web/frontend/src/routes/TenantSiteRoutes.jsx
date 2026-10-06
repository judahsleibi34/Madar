import { lazy, useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";

import RouteSuspense from "../components/common/RouteSuspense";
import { buildCanonicalTenantUrl, getBrandedMadarSubdomain } from "../utils/hostedAddress";

const TenantSiteRuntime = lazy(() =>
  import("../components/PageBuilder/runtime/TenantSiteRuntime")
);
const EcommerceStorefront = lazy(() =>
  import("../components/EcommerceStore/EcommerceStorefront")
);

const ELearningAcademy = lazy(() => import("../components/ELearning/ELearningAcademy"));
const HostedAcademyLearning = lazy(() => import("../components/ELearning/ELearningAcademy").then(m => ({ default: m.HostedAcademyLearning })));

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
    <RouteSuspense label="Loading site" variant="tenant-runtime" delay={0}>
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
