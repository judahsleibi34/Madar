import { isDashboardRoutePath, isTenantSiteRoutePath } from "./routeUtils";

export function getRouteErrorSurface(pathname, { isAdminUser = false } = {}) {
  if (isTenantSiteRoutePath(pathname)) return "tenant-site";
  if (pathname.startsWith("/page-builder")) return "page-builder";
  if (pathname.startsWith("/builder-data")) return "data-analysis";
  if (isDashboardRoutePath(pathname)) return isAdminUser ? "admin" : "user-workspace";
  return "public";
}
