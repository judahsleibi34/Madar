import { getBrandedMadarSubdomain } from "./utils/hostedAddress";
import { startHostedTenantPreload } from "./tenantRuntimePreload";

// Select a route entry before loading its JavaScript and CSS graph.
if (getBrandedMadarSubdomain(window.location.hostname)) {
  // The tenant entry must be requested first: its stylesheets are inserted
  // when the import starts, and route stylesheets must follow them so the
  // cascade order stays exactly as it is without preloading.
  import("./tenantMain.jsx");
  // Start the hosted route's code and primary read alongside the tenant entry.
  startHostedTenantPreload();
} else {
  import("./appMain.jsx");
}
