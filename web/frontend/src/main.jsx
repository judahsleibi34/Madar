import { getBrandedMadarSubdomain } from "./utils/hostedAddress";

// Select a route entry before loading its JavaScript and CSS graph.
if (getBrandedMadarSubdomain(window.location.hostname)) {
  import("./tenantMain.jsx");
} else {
  import("./appMain.jsx");
}
