import { isDashboardRoutePath, isTenantSiteRoutePath } from "./routeUtils";

export function getRouteErrorSurface(pathname, { isAdminUser = false } = {}) {
  if (isTenantSiteRoutePath(pathname)) return "tenant-site";
  if (pathname.startsWith("/page-builder")) return "page-builder";
  if (pathname.startsWith("/data-projects")) return "data-analysis";
  if (pathname.startsWith("/data-sources")) return "data-analysis";
  if (pathname.startsWith("/business-intelligence")) return "data-analysis";
  if (pathname.startsWith("/builder-data")) return "data-analysis";
  if (isDashboardRoutePath(pathname)) return isAdminUser ? "admin" : "user-workspace";
  return "public";
}
