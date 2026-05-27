export const sanitizeSubdomain = (value = "") => {
  return String(value)
    .toLowerCase()
    .trim()
    .replace(/https?:\/\//g, "")
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 63);
};

export const getProjectSubdomain = (project) => {
  const saved = project?.publish?.subdomain;
  const fallback = project?.name || "my-site";

  return sanitizeSubdomain(saved || fallback) || "my-site";
};

export const getLocalTenantPath = (project, path = "/") => {
  const subdomain = getProjectSubdomain(project);
  const cleanPath = path.startsWith("/") ? path : `/${path}`;

  return `/site/${subdomain}${cleanPath}`;
};

export const getProductionTenantUrl = (project, path = "/") => {
  const subdomain = getProjectSubdomain(project);
  const baseDomain = project?.publish?.siteBaseDomain || "madar.app";
  const customDomain = project?.publish?.customDomain;
  const cleanPath = path.startsWith("/") ? path : `/${path}`;

  if (customDomain) {
    return `https://${customDomain}${cleanPath}`;
  }

  return `https://${subdomain}.${baseDomain}${cleanPath}`;
};

export const getTenantLoginTarget = (project) => {
  const loginPath = project?.siteChrome?.authPageSlug || "/login";

  if (import.meta.env.DEV) {
    return getLocalTenantPath(project, loginPath);
  }

  return getProductionTenantUrl(project, loginPath);
};
