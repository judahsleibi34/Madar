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

export const getBuilderProjectBasePath = (projectId, workspace = "page-builder") =>
  `/${workspace}/projects/${encodeURIComponent(String(projectId || ""))}`;

export const getBuilderWorkspacePath = (projectId, tabId = "design", workspace = "page-builder") =>
  `${getBuilderProjectBasePath(projectId, workspace)}/${workspaceSegments[tabId] || workspaceSegments.design}`;

export const getBuilderProjectIdFromPath = (pathname = "") => {
  const match = String(pathname).match(/^\/(?:page-builder|builder-responses|builder-data)\/projects\/([^/?#]+)/);
  return match ? decodeURIComponent(match[1]) : "";
};

export const getBuilderWorkspaceFromPath = (pathname = "") => {
  const match = String(pathname).match(/^\/(page-builder|builder-responses|builder-data)(?:[/?#]|$)/);
  return match?.[1] || "page-builder";
};
