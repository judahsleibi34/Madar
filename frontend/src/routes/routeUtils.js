export function normalizeUserType(value) {
  return String(value || "user").trim().toLowerCase();
}

export function isTenantSiteRoutePath(pathname) {
  return pathname.startsWith("/site/");
}

export function isDashboardRoutePath(pathname) {
  return (
    pathname.startsWith("/dashboard") ||
    pathname.startsWith("/page-builder") ||
    pathname.startsWith("/builder-responses") ||
    pathname.startsWith("/builder-data") ||
    pathname.startsWith("/notifications") ||
    pathname.startsWith("/my-plan") ||
    pathname.startsWith("/admin/users") ||
    pathname.startsWith("/admin/account-access") ||
    pathname.startsWith("/settings")
  );
}

export function getSafePostLoginPath(userInfo, returnTo) {
  const nextUserType = normalizeUserType(userInfo?.user_type);
  const nextUserIsAdmin = nextUserType === "admin";

  let nextPath =
    returnTo && returnTo.startsWith("/") && !returnTo.startsWith("//")
      ? returnTo
      : "/dashboard";

  const adminOnlyPaths = ["/admin/users", "/admin/account-access"];

  const userOnlyPaths = [
    "/page-builder",
    "/builder-responses",
    "/builder-data",
    "/my-plan",
    "/settings",
  ];

  const isAdminOnlyPath = adminOnlyPaths.some((path) =>
    nextPath.startsWith(path)
  );

  const isUserOnlyPath = userOnlyPaths.some((path) =>
    nextPath.startsWith(path)
  );

  if (nextUserIsAdmin && isUserOnlyPath) {
    nextPath = "/dashboard";
  }

  if (!nextUserIsAdmin && isAdminOnlyPath) {
    nextPath = "/dashboard";
  }

  return nextPath;
}
