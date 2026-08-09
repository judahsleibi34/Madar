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
import { LanguageProvider } from "./i18n";
import "./styles/index.css";
import "./styles/admin/authenticated-reference.css";
import App from "./App.jsx";
import { getBrandedRuntimePath } from "./utils/hostedAddress";
import { installMadarPwaMetadata, isMadarPwaHost } from "./pwa/pwaContext";
import { getMadarServiceWorkerRegistration } from "./pwa/serviceWorker";

const brandedRuntimePath = getBrandedRuntimePath(window.location);
const madarPwaHost = isMadarPwaHost(window.location);

if (madarPwaHost) {
  installMadarPwaMetadata(document);

  // Avoid development workers controlling Vite's mutable module graph. The
  // explicit Push action can still register the worker when a developer tests it.
  if (import.meta.env.PROD) {
    getMadarServiceWorkerRegistration().catch((error) => {
      console.warn("Madar service worker registration failed:", error);
    });
  }
}

if (brandedRuntimePath) {
  window.history.replaceState(
    null,
    "",
    `${brandedRuntimePath}${window.location.search}${window.location.hash}`
  );
}

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <LanguageProvider>
        <App />
      </LanguageProvider>
    </BrowserRouter>
  </StrictMode>
);
