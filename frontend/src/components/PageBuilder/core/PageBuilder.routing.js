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

export const RESERVED_PUBLIC_PAGE_SLUGS = new Set([
  "admin",
  "api",
  "auth",
  "builder",
  "dashboard",
  "forgot-password",
  "login",
  "reset-password",
  "settings",
  "signup",
  "verify-email",
]);

const slugifyPageSegment = (value = "") => String(value)
  .toLowerCase()
  .trim()
  .replace(/^\/+|\/+$/g, "")
  .replace(/[^a-z0-9-]+/g, "-")
  .replace(/-{2,}/g, "-")
  .replace(/^-+|-+$/g, "")
  .slice(0, 80);

export const normalizePublicPageSlug = (value, fallbackName = "page") => {
  if (String(value || "").trim() === "/") return "/";
  const segment = slugifyPageSegment(value) || slugifyPageSegment(fallbackName) || "page";
  return `/${segment}`;
};

export const getDefaultPublicPage = (pages = [], defaultPageId = "") => {
  const explicitId = String(defaultPageId || "").trim();
  return (
    pages.find((page) => String(page?.id || "") === explicitId) ||
    pages.find((page) => page?.isDefault === true || page?.is_default === true) ||
    pages.find((page) => String(page?.slug || page?.path || "").trim() === "/") ||
    pages.find((page) => String(page?.name || page?.title || "").trim().toLowerCase() === "home") ||
    pages[0] ||
    null
  );
};

export const normalizeProjectPageRouting = (project = {}) => {
  const sourcePages = Array.isArray(project.pages) ? project.pages : [];
  const defaultPage = getDefaultPublicPage(sourcePages, project.defaultPageId);
  const defaultPageId = String(defaultPage?.id || "");
  const usedSlugs = new Set(["/"]);
  const pages = sourcePages.map((page, index) => {
    const isDefault = String(page?.id || "") === defaultPageId;
    if (isDefault) {
      return { ...page, slug: "/", isDefault: true, order: index };
    }

    const rawSlug = String(page?.slug || page?.path || "").trim();
    const fallback = page?.name || page?.title || `page-${index + 1}`;
    const baseSlug = normalizePublicPageSlug(rawSlug === "/" ? fallback : rawSlug, fallback);
    let slug = baseSlug;
    let suffix = 2;
    while (usedSlugs.has(slug)) {
      slug = `${baseSlug}-${suffix}`;
      suffix += 1;
    }
    usedSlugs.add(slug);
    return { ...page, slug, isDefault: false, order: index };
  });

  return { ...project, pages, defaultPageId };
};

export const setProjectDefaultPage = (project, pageId) =>
  normalizeProjectPageRouting({
    ...project,
    defaultPageId: String(pageId || ""),
    pages: (project?.pages || []).map((page) => ({
      ...page,
      isDefault: String(page?.id || "") === String(pageId || ""),
    })),
  });

export const getPublicPagePath = (basePath, page) => {
  const cleanBase = String(basePath || "").replace(/\/+$/, "");
  return page?.isDefault || page?.slug === "/"
    ? `${cleanBase}/`
    : `${cleanBase}${normalizePublicPageSlug(page?.slug, page?.name)}`;
};

export const resolvePublicPageByPath = (pages, path, defaultPageId = "") => {
  const normalizedPath = String(path || "/").replace(/\/+$/, "") || "/";
  if (normalizedPath === "/") return getDefaultPublicPage(pages, defaultPageId);
  return (pages || []).find(
    (page) => normalizePublicPageSlug(page?.slug, page?.name) === normalizedPath
  ) || null;
};

export const collectPublicPageRoutingIssues = (project = {}) => {
  const issues = [];
  const pages = Array.isArray(project.pages) ? project.pages : [];
  const defaultPages = pages.filter((page) => page?.isDefault === true);
  if (pages.length && defaultPages.length !== 1) {
    issues.push({ issue_type: "missing_default_page", page_count: pages.length });
  }
  const occurrences = new Map();
  pages.forEach((page) => {
    const slug = normalizePublicPageSlug(page?.slug, page?.name);
    const segment = slug.replace(/^\//, "");
    const context = {
      page_id: String(page?.id || ""),
      page_name: String(page?.name || page?.title || "Untitled page"),
      page_slug: slug,
    };
    if (!page?.isDefault && RESERVED_PUBLIC_PAGE_SLUGS.has(segment)) {
      issues.push({ issue_type: "reserved_page_slug", ...context });
    }
    occurrences.set(slug, [...(occurrences.get(slug) || []), context]);
  });
  occurrences.forEach((pagesForSlug, slug) => {
    if (pagesForSlug.length > 1) {
      issues.push({
        issue_type: "duplicate_page_slug",
        duplicate_slug: slug,
        occurrences: pagesForSlug,
      });
    }
  });
  return issues;
};

export const getConfiguredProjectSubdomain = (project) => {
  return sanitizeSubdomain(project?.publish?.subdomain || "");
};

export const getProjectSubdomain = (project) => {
  const saved = getConfiguredProjectSubdomain(project);
  const fallback = project?.name || "my-site";

  return saved || sanitizeSubdomain(fallback) || "my-site";
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
