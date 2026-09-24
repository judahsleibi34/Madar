export const RESERVED_MADAR_HOSTS = new Set([
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
  const cleanHost = String(hostname || "").trim().toLowerCase().replace(/\.$/, "").split(":", 1)[0];
  const cleanDomain = String(publicDomain || "").trim().toLowerCase().replace(/^\.+|\.+$/g, "");
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

export const buildCanonicalTenantUrl = (
  tenant,
  path = "/",
  publicDomain = import.meta.env.VITE_PUBLIC_SITE_DOMAIN || "madarportal.com"
) => {
  const cleanTenant = String(tenant || "").trim().toLowerCase();
  const cleanDomain = String(publicDomain || "").trim().toLowerCase().replace(/^\.+|\.+$/g, "");
  if (
    !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(cleanTenant) ||
    RESERVED_MADAR_HOSTS.has(cleanTenant) ||
    !cleanDomain
  ) return "";
  const cleanPath = String(path || "/");
  return `https://${cleanTenant}.${cleanDomain}${cleanPath.startsWith("/") ? cleanPath : `/${cleanPath}`}`;
};

// Kept as a compatibility export for callers outside the application bundle.
// Canonical tenant routing must never rewrite the browser path.
export const getBrandedRuntimePath = (locationLike) => {
  void locationLike;
  return "";
};
