import { getBrandedMadarSubdomain } from "./utils/hostedAddress";
import { installModuleReload, isModuleLoadError, reloadOnce } from "./utils/moduleReload";

installModuleReload();
const recoverEntry = error => { if (isModuleLoadError(error)) reloadOnce(); };

// Select a route entry before loading its JavaScript and CSS graph.
if (getBrandedMadarSubdomain(window.location.hostname)) {
  import("./tenantMain.jsx").catch(recoverEntry);
} else {
  import("./appMain.jsx").catch(recoverEntry);
}
