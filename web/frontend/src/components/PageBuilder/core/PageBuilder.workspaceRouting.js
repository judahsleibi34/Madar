const workspaceSegments = Object.freeze({
  design: "pages",
  forms: "forms",
  reservations: "reservations",
  chrome: "header-footer",
  users: "users",
  theme: "website-theme",
  publish: "publish",
  data: "data",
  responses: "responses",
  workflows: "workflows",
});

// Legacy editor paths share the project-route segments; reverse aliases remain explicit.
export const builderTabPathById = Object.fromEntries(
  Object.entries(workspaceSegments).map(([tabId, segment]) => [tabId, `/page-builder/${segment}`])
);

export const builderDesignPanelPathById = {
  Pages: "/page-builder/pages",
  Sections: "/page-builder/pages/sections",
  Themes: "/page-builder/pages/themes",
};

const builderTabIdByPathSegment = {
  pages: "design",
  design: "design",
  forms: "forms",
  reservations: "reservations",
  chrome: "chrome",
  "header-footer": "chrome",
  header: "chrome",
  footer: "chrome",
  users: "users",
  theme: "design",
  themes: "design",
  "website-theme": "design",
  "site-theme": "design",
  publish: "publish",
  data: "data",
  responses: "responses",
  workflows: "workflows",
};

export const getBuilderTabFromPath = (pathname = "") => {
  const match = pathname.match(/^\/(?:page-builder|e-learning\/landing-page)\/(?:projects\/[^/?#]+\/)?([^/?#]+)/);
  if (!match) return null;
  return builderTabIdByPathSegment[match[1]] || null;
};

export const getBuilderDesignPanelFromPath = (pathname = "") => {
  const builderPath = String(pathname).replace(/^\/(?:page-builder|e-learning\/landing-page)\/projects\/[^/?#]+/, "/page-builder");
  if (/^\/page-builder\/(?:theme|themes|website-theme|site-theme)(?:[/?#]|$)/.test(builderPath)) {
    return "Themes";
  }
  const match = builderPath.match(/^\/page-builder\/(?:pages|design)\/([^/?#]+)/);
  if (match?.[1] === "themes") return "Themes";
  if (match?.[1] === "sections") return "Sections";
  return "Pages";
};

export const getBuilderProjectBasePath = (projectId, workspace = "page-builder") =>
  `/${workspace}/projects/${encodeURIComponent(String(projectId || ""))}`;

export const getBuilderWorkspacePath = (projectId, tabId = "design", workspace = "page-builder") =>
  `${getBuilderProjectBasePath(projectId, workspace)}/${workspaceSegments[tabId] || workspaceSegments.design}`;

export const getBuilderProjectIdFromPath = (pathname = "") => {
  const match = String(pathname).match(/^\/(?:e-learning\/landing-page|page-builder|builder-responses|data-sources|business-intelligence|builder-data)\/projects\/([^/?#]+)/);
  return match ? decodeURIComponent(match[1]) : "";
};

export const getBuilderWorkspaceFromPath = (pathname = "") => {
  const match = String(pathname).match(/^\/(e-learning\/landing-page|page-builder|builder-responses|data-sources|business-intelligence|builder-data)(?:[/?#]|$)/);
  return match?.[1] || "page-builder";
};
