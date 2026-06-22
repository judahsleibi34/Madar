import { createInitialProject } from "./PageBuilder.starters";
import { defaultSiteChrome } from "./PageBuilder.constants";
import { internalPageNames } from "./PageBuilder.copy";
import {
  getSectionElements,
  isMetricsSection,
  isResponsesSection,
  removeDeprecatedBuilderElements,
  hasFormSection,
  removeDuplicateFormHeadings,
  convertSectionToDirectLayout,
  mergeSectionsIntoPageCanvas,
} from "./PageBuilder.layout";

export const normalizeBuilderProjectShape = (project) => {
  const fallback = createInitialProject();
  const source =
    project && typeof project === "object" && !Array.isArray(project)
      ? project
      : {};

  const pages =
    Array.isArray(source.pages) && source.pages.length > 0
      ? source.pages
      : fallback.pages;

  const forms =
    Array.isArray(source.forms) && source.forms.length > 0
      ? source.forms
      : fallback.forms;

  const workflows = Array.isArray(source.workflows)
    ? source.workflows
    : fallback.workflows || [];

  const roles = Array.isArray(source.roles) ? source.roles : fallback.roles || [];
  const users = Array.isArray(source.users) ? source.users : fallback.users || [];
  const collections = Array.isArray(source.collections)
    ? source.collections
    : fallback.collections || [];

  return {
    ...fallback,
    ...source,
    pages,
    forms,
    workflows,
    roles,
    users,
    collections,
    activePageId: pages.some((page) => page.id === source.activePageId)
      ? source.activePageId
      : pages[0]?.id || "",
    activeFormId: forms.some((form) => form.id === source.activeFormId)
      ? source.activeFormId
      : forms[0]?.id || "",
    activeWorkflowId: workflows.some(
      (workflow) => workflow.id === source.activeWorkflowId
    )
      ? source.activeWorkflowId
      : workflows[0]?.id || "",
    activeRoleId: roles.some((role) => role.id === source.activeRoleId)
      ? source.activeRoleId
      : roles[0]?.id || "",
    siteChrome: {
      ...(fallback.siteChrome || defaultSiteChrome),
      ...(source.siteChrome || {}),
    },
    theme: {
      ...(fallback.theme || {}),
      ...(source.theme || {}),
    },
  };
};

export const cleanBuilderProject = (project) => {
  const normalizedProject = normalizeBuilderProjectShape(project);

  if (!normalizedProject.pages.length) return normalizedProject;

  const formSectionsToKeep = normalizedProject.pages
    .slice(1)
    .flatMap((page) => page.sections || [])
    .filter((section) =>
      getSectionElements(section).some((element) => element.type === "formBlock")
    );

  const cleanedPages = normalizedProject.pages
    .filter(
      (page, index) =>
        index === 0 ||
        !internalPageNames.has(String(page.name || "").toLowerCase())
    )
    .map((page, index) => {
      const baseSections = (page.sections || [])
        .filter(
          (section) =>
            !isMetricsSection(section) &&
            !(isResponsesSection(section) && !section.isPageCanvas)
        )
        .map(removeDeprecatedBuilderElements);

      const sections =
        index === 0 && !hasFormSection({ ...page, sections: baseSections })
          ? [...baseSections, ...formSectionsToKeep]
          : baseSections;

      const normalizedSections = sections.map((section) =>
        convertSectionToDirectLayout(removeDuplicateFormHeadings(section))
      );

      return mergeSectionsIntoPageCanvas({
        ...page,
        showInNavigation: index === 0 ? true : page.showInNavigation,
      }, normalizedSections);
    });

  const pages = cleanedPages.length ? cleanedPages : normalizedProject.pages;

  return {
    ...normalizedProject,
    directLayoutVersion: 4,
    activePageId: pages.some((page) => page.id === normalizedProject.activePageId)
      ? normalizedProject.activePageId
      : pages[0]?.id || "",
    siteChrome: {
      ...normalizedProject.siteChrome,
      footerShopLinks: String(normalizedProject.siteChrome?.footerShopLinks || "")
        .split("\n")
        .filter((item) => !["Responses", "Reports", "Orders"].includes(item.trim()))
        .join("\n"),
    },
    pages,
  };
};

export const normalizeProjectSlug = (value) => {
  const cleanValue = String(value || "")
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9-]/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+|-+$/g, "");

  return cleanValue || `builder-project-${Date.now()}`;
};

export const getBuilderProjectName = (project) =>
  String(project?.name || project?.siteChrome?.brandName || "Page Builder Project").trim() ||
  "Page Builder Project";

export const getBuilderProjectSlug = (project, record) =>
  normalizeProjectSlug(record?.slug || project?.slug || project?.siteChrome?.subdomain || project?.siteChrome?.brandName || project?.name);

export const getDraftProjectFromRecord = (record) => {
  if (!record?.draft_schema || typeof record.draft_schema !== "object" || Array.isArray(record.draft_schema)) {
    return null;
  }

  return cleanBuilderProject(record.draft_schema);
};

export const getPreviewCanvasStyle = (viewport, isPreview, viewports) => {
  if (isPreview && viewport === "desktop") {
    return { width: "100%" };
  }

  const viewportWidth = viewports[viewport] || viewports.desktop;

  return {
    width: `${viewportWidth}px`,
    maxWidth: "100%",
  };
};

