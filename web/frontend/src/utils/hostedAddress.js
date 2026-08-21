const RESERVED_MADAR_HOSTS = new Set([
  "admin",
  "api",
  "app",
  "auth",
  "billing",
  "cdn",
  "dashboard",
  "forms",
  "health",
  "login",
  "logout",
  "mail",
  "pricing",
  "privacy-policy",
  "public",
  "signup",
  "site",
  "static",
  "terms-and-conditions",
  "www",
]);

export const getBrandedMadarSubdomain = (
  hostname,
  publicDomain = import.meta.env.VITE_PUBLIC_SITE_DOMAIN || "madarportal.com"
) => {
  const cleanHost = String(hostname || "").trim().toLowerCase().split(":", 1)[0];
  const cleanDomain = String(publicDomain || "").trim().toLowerCase();
  if (!cleanHost || !cleanDomain || cleanHost === cleanDomain) return "";
  const suffix = `.${cleanDomain}`;
  if (!cleanHost.endsWith(suffix)) return "";
  const candidate = cleanHost.slice(0, -suffix.length);
  if (
    !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(candidate) ||
    RESERVED_MADAR_HOSTS.has(candidate)
  ) {
    return "";
  }
  return candidate;
};

export const getBrandedRuntimePath = (locationLike) => {
  const subdomain = getBrandedMadarSubdomain(locationLike?.hostname);
  if (!subdomain) return "";
  const pathname = String(locationLike?.pathname || "/");
  if (
    pathname === "/shop" ||
    pathname.startsWith("/shop/") ||
    pathname.startsWith("/site/") ||
    pathname.startsWith("/api/")
  ) return "";
  return `/site/${encodeURIComponent(subdomain)}${pathname.startsWith("/") ? pathname : `/${pathname}`}`;
};