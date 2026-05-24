// Add these imports to your router/App.jsx file:
import TenantSiteRuntime from "./components/PageBuilder/TenantSiteRuntime";

// Add this route inside <Routes>:
<Route path="/site/:subdomain/*" element={<TenantSiteRuntime />} />
