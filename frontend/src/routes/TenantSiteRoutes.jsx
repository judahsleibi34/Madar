import { Navigate, Route, Routes } from "react-router-dom";

import TenantSiteRuntime from "../components/PageBuilder/runtime/TenantSiteRuntime";

export default function TenantSiteRoutes() {
  return (
    <Routes>
      <Route path="/site/:subdomain/*" element={<TenantSiteRuntime />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
