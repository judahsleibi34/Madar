import { lazy } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import RouteSuspense from "../components/common/RouteSuspense";

const TenantSiteRuntime = lazy(() =>
  import("../components/PageBuilder/runtime/TenantSiteRuntime")
);
const EcommerceStorefront = lazy(() =>
  import("../components/EcommerceStore/EcommerceStorefront")
);

export default function TenantSiteRoutes() {
  return (
    <RouteSuspense label="Loading site" variant="tenant-runtime">
      <Routes>
        <Route path="/forms/:subdomain/:formId" element={<TenantSiteRuntime />} />
        <Route path="/site/:subdomain/shop/*" element={<EcommerceStorefront />} />
        <Route path="/site/:subdomain/*" element={<TenantSiteRuntime />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </RouteSuspense>
  );
}
