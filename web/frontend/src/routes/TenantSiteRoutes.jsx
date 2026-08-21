import { lazy } from "react";
import { Navigate, Route, Routes, useLocation, useParams } from "react-router-dom";

import RouteSuspense from "../components/common/RouteSuspense";
import { getBrandedMadarSubdomain } from "../utils/hostedAddress";

const TenantSiteRuntime = lazy(() =>
  import("../components/PageBuilder/runtime/TenantSiteRuntime")
);
const EcommerceStorefront = lazy(() =>
  import("../components/EcommerceStore/EcommerceStorefront")
);

function LegacyStoreRedirect() {
  const { subdomain = "", "*": routeTail = "" } = useParams();
  const location = useLocation();
  const cleanTail = String(routeTail || "").replace(/^\/+/, "");
  const target = `/store/${encodeURIComponent(subdomain)}${cleanTail ? `/${cleanTail}` : ""}${location.search}${location.hash}`;
  return <Navigate to={target} replace />;
}

function BrandedStorefront() {
  const subdomain = getBrandedMadarSubdomain(window.location.hostname);
  if (!subdomain) return <Navigate to="/" replace />;
  return <EcommerceStorefront subdomain={subdomain} basePath="/shop" />;
}

export default function TenantSiteRoutes() {
  return (
    <RouteSuspense label="Loading site" variant="tenant-runtime">
      <Routes>
        <Route path="/forms/:subdomain/:formId" element={<TenantSiteRuntime />} />
        <Route path="/store/:subdomain/*" element={<EcommerceStorefront />} />
        <Route path="/shop/*" element={<BrandedStorefront />} />
        <Route path="/site/:subdomain/shop/*" element={<LegacyStoreRedirect />} />
        <Route path="/site/:subdomain/*" element={<TenantSiteRuntime />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </RouteSuspense>
  );
}