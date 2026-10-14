import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-700.css";
import "@fontsource/inter/latin-800.css";
import "@fontsource/inter/latin-900.css";
import "@fontsource/ibm-plex-sans-arabic/arabic-400.css";
import "@fontsource/ibm-plex-sans-arabic/arabic-500.css";
import "@fontsource/ibm-plex-sans-arabic/arabic-600.css";
import "@fontsource/ibm-plex-sans-arabic/arabic-700.css";
import "@fontsource/lobster-two/latin-400.css";
import "@fontsource/lobster-two/latin-400-italic.css";
import "@fontsource/lobster-two/latin-700.css";
import "@fontsource/lobster-two/latin-700-italic.css";
import "@fontsource/eb-garamond/latin-400.css";
import "@fontsource/eb-garamond/latin-400-italic.css";
import "@fontsource/eb-garamond/latin-500.css";
import "@fontsource/eb-garamond/latin-600.css";
import "@fontsource/eb-garamond/latin-700.css";
import "@fontsource/eb-garamond/latin-700-italic.css";
import "@fontsource/cormorant-garamond/latin-400.css";
import "@fontsource/cormorant-garamond/latin-400-italic.css";
import "@fontsource/cormorant-garamond/latin-500-italic.css";
import "@fontsource/cormorant-garamond/latin-700.css";
import "@fontsource/playfair-display/latin-400.css";
import "@fontsource/playfair-display/latin-400-italic.css";
import "@fontsource/playfair-display/latin-500-italic.css";
import "@fontsource/playfair-display/latin-700.css";
import "@fontsource/lora/latin-400.css";
import "@fontsource/lora/latin-400-italic.css";
import "@fontsource/lora/latin-500-italic.css";
import "@fontsource/lora/latin-700.css";
import "@fontsource/montserrat/latin-400.css";
import "@fontsource/montserrat/latin-400-italic.css";
import "@fontsource/montserrat/latin-500-italic.css";
import "@fontsource/montserrat/latin-700.css";
import "@fontsource/poppins/latin-400.css";
import "@fontsource/poppins/latin-400-italic.css";
import "@fontsource/poppins/latin-500-italic.css";
import "@fontsource/poppins/latin-700.css";
import "@fontsource/raleway/latin-400.css";
import "@fontsource/raleway/latin-400-italic.css";
import "@fontsource/raleway/latin-500-italic.css";
import "@fontsource/raleway/latin-700.css";
import "@fontsource/oswald/latin-400.css";
import "@fontsource/oswald/latin-500.css";
import "@fontsource/oswald/latin-700.css";
import "@fontsource/bebas-neue/latin-400.css";
import i18n, { ensureTranslations, LanguageProvider, registerTranslationBundles } from "./i18n";
import TenantSiteRoutes from "./routes/TenantSiteRoutes";
import {
  getHostedTenantRuntime,
  getInitialTenantTranslations,
  ROUTE_TRANSLATION_NAMESPACES,
  whenPrimaryReadSettled,
} from "./tenantRuntimePreload";
import "./styles/tenant-entry.css";

const renderTenant = () => {
  createRoot(document.getElementById("root")).render(
    <StrictMode>
      <BrowserRouter>
        <LanguageProvider>
          <TenantSiteRoutes />
        </LanguageProvider>
      </BrowserRouter>
    </StrictMode>,
  );
};

// The entry started this route's translations alongside the tenant code.
// Register them before the first render; if that download failed, each route
// loads its own namespaces again before it renders.
getInitialTenantTranslations()
  .then(registerTranslationBundles, () => {})
  .then(renderTenant);

// The storefront switches language in place; keep that switch instant by
// fetching the other language once the page is idle.
// It waits for the storefront's primary read so it never competes with it.
if (getHostedTenantRuntime()?.kind === "store") {
  const prefetchOtherLanguage = () => {
    const other = i18n.language === "ar" ? "en" : "ar";
    ensureTranslations(ROUTE_TRANSLATION_NAMESPACES.store, other)?.catch(() => {});
  };
  whenPrimaryReadSettled().then(() => {
    if (typeof window.requestIdleCallback === "function") window.requestIdleCallback(prefetchOtherLanguage, { timeout: 4000 });
    else window.setTimeout(prefetchOtherLanguage, 2000);
  });
}
