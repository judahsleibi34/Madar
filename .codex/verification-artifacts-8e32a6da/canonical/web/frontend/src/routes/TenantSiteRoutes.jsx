import { lazy, useEffect } from "react";
import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";

import RouteSuspense from "../components/common/RouteSuspense";
import { preloadPublicEcommerceCatalog } from "../services/ecommerceApi";
import { getBrandedMadarSubdomain } from "../utils/hostedAddress";

const TenantSiteRuntime = lazy(() =>
  import("../components/PageBuilder/runtime/TenantSiteRuntime")
);
const EcommerceStorefront = lazy(() =>
  import("../components/EcommerceStore/EcommerceStorefront")
);

function ConnectedSiteStorefront() {
  const { subdomain = "" } = useParams();
  const basePath = `/site/${encodeURIComponent(subdomain)}/shop`;
  return <EcommerceStorefront subdomain={subdomain} basePath={basePath} />;
}

function BrandedStorefront() {
  const subdomain = getBrandedMadarSubdomain(window.location.hostname);
  if (!subdomain) return <Navigate to="/" replace />;
  return <EcommerceStorefront subdomain={subdomain} basePath="/shop" />;
}

export default function TenantSiteRoutes() {
  const location = useLocation();
  const siteMatch = location.pathname.match(/^\/site\/([^/]+)(?:\/|$)/i);
  const currentSubdomain = siteMatch ? decodeURIComponent(siteMatch[1]) : "";
  const isShopRoute = /^\/site\/[^/]+\/shop(?:\/|$)/i.test(location.pathname);

  useEffect(() => {
    if (!currentSubdomain || isShopRoute) return undefined;
    const preload = () => {
      import("../components/EcommerceStore/EcommerceStorefront");
      preloadPublicEcommerceCatalog(currentSubdomain);
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
        <Route path="/forms/:subdomain/:formId" element={<TenantSiteRuntime />} />
        <Route path="/store/:subdomain/*" element={<EcommerceStorefront />} />
        <Route path="/shop/*" element={<BrandedStorefront />} />
        <Route path="/site/:subdomain/shop/*" element={<ConnectedSiteStorefront />} />
        <Route path="/site/:subdomain/*" element={<TenantSiteRuntime />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </RouteSuspense>
  );
}
