import { DASHBOARD_ROUTES, POST_LOGIN_FALLBACK_ROUTE } from "../config/routes";

export function normalizeUserType(value) {
  return String(value || "user").trim().toLowerCase();
}

export function isTenantSiteRoutePath(pathname) {
  return pathname.startsWith("/site/") || pathname.startsWith("/forms/");
}

export function isDashboardRoutePath(pathname) {
  return (
    pathname.startsWith(DASHBOARD_ROUTES.dashboard) ||
    pathname.startsWith(DASHBOARD_ROUTES.pageBuilder) ||
    pathname.startsWith(DASHBOARD_ROUTES.builderResponses) ||
    pathname.startsWith(DASHBOARD_ROUTES.builderData) ||
    pathname.startsWith(DASHBOARD_ROUTES.calendar) ||
    pathname.startsWith(DASHBOARD_ROUTES.archive) ||
    pathname.startsWith(DASHBOARD_ROUTES.notifications) ||
    pathname.startsWith(DASHBOARD_ROUTES.myPlan) ||
    pathname.startsWith(DASHBOARD_ROUTES.adminUsers) ||
    pathname.startsWith(DASHBOARD_ROUTES.adminAccountAccess) ||
    pathname.startsWith(DASHBOARD_ROUTES.settings)
  );
}

export function getSafePostLoginPath(userInfo, returnTo) {
  const nextUserType = normalizeUserType(userInfo?.user_type);
  const nextUserIsAdmin = nextUserType === "admin";

  let nextPath =
    returnTo && returnTo.startsWith("/") && !returnTo.startsWith("//")
      ? returnTo
      : POST_LOGIN_FALLBACK_ROUTE;

  const adminOnlyPaths = [
    DASHBOARD_ROUTES.adminUsers,
    DASHBOARD_ROUTES.adminAccountAccess,
  ];

  const userOnlyPaths = [
    DASHBOARD_ROUTES.pageBuilder,
    DASHBOARD_ROUTES.builderResponses,
    DASHBOARD_ROUTES.builderData,
    DASHBOARD_ROUTES.calendar,
    DASHBOARD_ROUTES.archive,
    DASHBOARD_ROUTES.myPlan,
  ];

  const isAdminOnlyPath = adminOnlyPaths.some((path) =>
    nextPath.startsWith(path)
  );

  const isUserOnlyPath = userOnlyPaths.some((path) =>
    nextPath.startsWith(path)
  );

  if (nextUserIsAdmin && isUserOnlyPath) {
    nextPath = POST_LOGIN_FALLBACK_ROUTE;
  }

  if (!nextUserIsAdmin && isAdminOnlyPath) {
    nextPath = POST_LOGIN_FALLBACK_ROUTE;
  }

  return nextPath;
}
