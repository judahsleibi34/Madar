import { createBlankWorkspaceProject } from "./PageBuilder.starters";
import { defaultSiteChrome } from "./PageBuilder.constants";
import { internalPageNames } from "./PageBuilder.copy";
import {
  createElement,
  createColumn,
  createRow,
  createSection,
  createPage,
} from "./PageBuilder.factories";
import {
  getSectionElements,
  isResponsesSection,
  removeDeprecatedBuilderElements,
  hasFormSection,
  removeDuplicateFormHeadings,
  convertSectionToDirectLayout,
  mergeSectionsIntoPageCanvas,
} from "./PageBuilder.layout";

const normalizeBuilderElementShape = (element) => {
  if (!element || typeof element !== "object" || Array.isArray(element)) {
    return createElement("text");
  }

  const elementName = String(element.name || "").trim().toLowerCase();
  const elementContent = String(element.content || "").trim().toLowerCase();
  const isLegacyLoginCard =
    element.type === "card" &&
    elementName === "login form card" &&
    /^email address\s+password\s+login$/i.test(elementContent);

  if (isLegacyLoginCard) {
    return createElement("loginBlock", {
      ...element,
      type: "loginBlock",
      auth: {
        title: "Login to your account",
        subtitle: "Access your private dashboard, submissions, reports, and internal tools.",
        buttonText: "Login",
        switchText: "",
        switchActionText: "",
        ...(element.auth || {}),
      },
    });
  }

  return createElement(element.type || "text", element);
};

const normalizeBuilderColumnShape = (column) => {
  const source =
    column && typeof column === "object" && !Array.isArray(column)
      ? column
      : {};
  const elements = Array.isArray(source.elements)
    ? source.elements.map(normalizeBuilderElementShape)
    : [];

  return createColumn(elements, {
    ...source,
    name: source.name || "Column",
    layout: {
      align: "left",
      ...(source.layout || {}),
    },
    elements,
  });
};

const normalizeBuilderRowShape = (row) => {
  const source =
    row && typeof row === "object" && !Array.isArray(row)
      ? row
      : {};
  const columns = Array.isArray(source.columns) && source.columns.length > 0
    ? source.columns.map(normalizeBuilderColumnShape)
    : [normalizeBuilderColumnShape({ elements: source.elements || [] })];

  return createRow(columns, {
    ...source,
    layout: {
      columns: String(source.layout?.columns || columns.length || 1),
      align: source.layout?.align || "center",
      gap: source.layout?.gap || "medium",
      ...(source.layout || {}),
    },
    columns,
  });
};

const normalizeBuilderSectionShape = (section) => {
  const source =
    section && typeof section === "object" && !Array.isArray(section)
      ? section
      : {};
  const legacyElements = Array.isArray(source.elements) ? source.elements : [];
  const rows = Array.isArray(source.rows) && source.rows.length > 0
    ? source.rows.map(normalizeBuilderRowShape)
    : [normalizeBuilderRowShape({ elements: legacyElements })];
  const freeElements = Array.isArray(source.freeElements)
    ? source.freeElements.map(normalizeBuilderElementShape)
    : [];

  const base = createSection({
    name: source.name || source.type || "Section",
    mode: source.mode || "auto",
    layout: source.layout || {},
    rows,
    freeElements,
  });

  return {
    ...base,
    ...source,
    mode: source.mode || base.mode,
    layout: {
      ...base.layout,
      ...(source.layout || {}),
    },
    rows,
    freeElements,
  };
};

const normalizeBuilderPageShape = (page, fallbackPage) => {
  const source =
    page && typeof page === "object" && !Array.isArray(page)
      ? page
      : fallbackPage || {};
  const sections = Array.isArray(source.sections)
    ? source.sections.map(normalizeBuilderSectionShape)
    : [];

  return createPage(source.name || fallbackPage?.name || "Home", sections, {
    ...source,
    slug: source.slug || source.path || fallbackPage?.slug || "/",
    backgroundColor: source.backgroundColor || fallbackPage?.backgroundColor || "var(--theme-surface)",
    visibility: source.visibility || fallbackPage?.visibility || "public",
    showInNavigation:
      typeof source.showInNavigation === "boolean"
        ? source.showInNavigation
        : fallbackPage?.showInNavigation ?? true,
    pageType: source.pageType || fallbackPage?.pageType || "main",
    sections,
  });
};

export const normalizeBuilderProjectShape = (project) => {
  const fallback = createBlankWorkspaceProject();
  const source =
    project && typeof project === "object" && !Array.isArray(project)
      ? project
      : {};

  const sourcePages =
    Array.isArray(source.pages) && source.pages.length > 0
      ? source.pages
      : fallback.pages;
  const pages = sourcePages.map((page, index) =>
    normalizeBuilderPageShape(page, fallback.pages[index])
  );

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
  const forms = normalizedProject.forms.map((form) => ({
    ...form,
    responses: [],
  }));
  const collections = normalizedProject.collections.map((collection) => ({
    ...collection,
    records: [],
  }));

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
    forms,
    collections,
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

  return cleanBuilderProject({
    ...record.draft_schema,
    ...(record.status ? { status: record.status } : {}),
  });
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
