import { createBlankWorkspaceProject } from "./PageBuilder.starters";
import { createId, defaultSiteChrome } from "./PageBuilder.constants";
import { normalizeProjectPageRouting } from "./PageBuilder.routing";
import { normalizeElementAction } from "./PageBuilder.actions";
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
  removeDuplicateFormHeadings,
  convertSectionToDirectLayout,
  mergeSectionsIntoPageCanvas,
} from "./PageBuilder.layout";

export const normalizeFormReference = (value) => String(value ?? "").trim();
export const buildFormConnectionUpdate = (value) => ({
  connectedFormId: normalizeFormReference(value),
});

const nextUnusedId = (prefix, usedIds, idFactory) => {
  let candidate = "";
  do {
    candidate = String(idFactory(prefix) || "").trim();
  } while (!candidate || usedIds.has(candidate));
  return candidate;
};

export const repairDuplicateProjectIds = (project, { idFactory = createId } = {}) => {
  const source = project && typeof project === "object" && !Array.isArray(project)
    ? project
    : {};
  const repairs = [];
  const usedPageIds = new Set();
  const usedFormIds = new Set();
  const usedBlockIds = new Set();

  const repairId = ({ value, prefix, usedIds, kind, context }) => {
    const oldId = String(value ?? "").trim();
    if (oldId && !usedIds.has(oldId)) {
      usedIds.add(oldId);
      return oldId;
    }

    const newId = nextUnusedId(prefix, usedIds, idFactory);
    usedIds.add(newId);
    repairs.push({ kind, oldId, newId, ...context });
    return newId;
  };

  const repairElement = (element, page, occurrenceIndex) => {
    if (!element || typeof element !== "object" || Array.isArray(element)) return element;
    const nextId = repairId({
      value: element.id,
      prefix: "element",
      usedIds: usedBlockIds,
      kind: "block",
      context: {
        pageId: String(page?.id || ""),
        pageName: String(page?.name || page?.title || "Untitled page"),
        blockType: String(element.type || "unknown"),
        occurrenceIndex,
      },
    });
    return nextId === element.id ? element : { ...element, id: nextId };
  };

  let blockOccurrenceIndex = 0;
  const pages = (Array.isArray(source.pages) ? source.pages : []).map((page, pageIndex) => {
    if (!page || typeof page !== "object" || Array.isArray(page)) return page;
    const pageId = repairId({
      value: page.id,
      prefix: "page",
      usedIds: usedPageIds,
      kind: "page",
      context: { pageName: String(page.name || page.title || "Untitled page"), occurrenceIndex: pageIndex },
    });
    const pageContext = { ...page, id: pageId };
    const sections = (Array.isArray(page.sections) ? page.sections : []).map((section) => {
      if (!section || typeof section !== "object" || Array.isArray(section)) return section;
      const repairElements = (elements) => (Array.isArray(elements) ? elements : []).map((element) => {
        const repaired = repairElement(element, pageContext, blockOccurrenceIndex);
        blockOccurrenceIndex += 1;
        return repaired;
      });
      return {
        ...section,
        ...(Array.isArray(section.elements) ? { elements: repairElements(section.elements) } : {}),
        ...(Array.isArray(section.freeElements) ? { freeElements: repairElements(section.freeElements) } : {}),
        ...(Array.isArray(section.rows) ? {
          rows: section.rows.map((row) => ({
            ...row,
            columns: (Array.isArray(row?.columns) ? row.columns : []).map((column) => ({
              ...column,
              elements: repairElements(column?.elements),
            })),
          })),
        } : {}),
      };
    });
    return { ...page, id: pageId, sections };
  });

  const forms = (Array.isArray(source.forms) ? source.forms : []).map((form, formIndex) => {
    if (!form || typeof form !== "object" || Array.isArray(form)) return form;
    const id = repairId({
      value: form.id,
      prefix: "form",
      usedIds: usedFormIds,
      kind: "form",
      context: {
        formName: String(form.name || form.title || "Untitled form"),
        occurrenceIndex: formIndex,
      },
    });
    return id === form.id ? form : { ...form, id };
  });

  return {
    project: { ...source, pages, forms },
    repairs,
  };
};

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

  const { formId: legacyFormId, form_id: legacyFormIdSnake, ...canonicalElement } = element;
  const normalized = createElement(element.type || "text", canonicalElement);
  normalized.id = String(normalized.id || "");
  normalized.action = normalizeElementAction(element.action);
  if (normalized.type === "formBlock") {
    const reference = Object.hasOwn(element, "connectedFormId")
      ? element.connectedFormId
      : legacyFormId ?? legacyFormIdSnake;
    normalized.connectedFormId = normalizeFormReference(
      reference
    );
  }
  return normalized;
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
  const sourceFreeElements = Array.isArray(source.freeElements)
    ? source.freeElements
    : [];
  const freeElementIds = new Set(
    sourceFreeElements.map((element) => String(element?.id || "")).filter(Boolean)
  );
  const legacyElements = Array.isArray(source.elements)
    ? source.elements.filter(
        (element) => !freeElementIds.has(String(element?.id || ""))
      )
    : [];
  const rows = Array.isArray(source.rows) && source.rows.length > 0
    ? source.rows.map(normalizeBuilderRowShape)
    : [normalizeBuilderRowShape({ elements: legacyElements })];
  const freeElements = sourceFreeElements.map(normalizeBuilderElementShape);
  const canonicalSource = Object.fromEntries(
    Object.entries(source).filter(([key]) => key !== "elements")
  );

  const base = createSection({
    name: source.name || source.type || "Section",
    mode: source.mode || "auto",
    layout: source.layout || {},
    rows,
    freeElements,
  });

  return {
    ...base,
    ...canonicalSource,
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

  const normalizedPage = createPage(source.name || fallbackPage?.name || "Home", sections, {
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
  return { ...normalizedPage, id: String(normalizedPage.id || "") };
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
  const normalizedPages = sourcePages.map((page, index) =>
    normalizeBuilderPageShape(page, fallback.pages[index])
  );
  const routedProject = normalizeProjectPageRouting({
    ...source,
    pages: normalizedPages,
  });
  const pages = routedProject.pages;

  const forms = (
    Array.isArray(source.forms)
      ? source.forms
      : fallback.forms
  ).map((form) => ({ ...form, id: String(form?.id || "") }));

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
    defaultPageId: routedProject.defaultPageId,
    forms,
    workflows,
    roles,
    users,
    collections,
    activePageId: pages.some((page) => page.id === String(source.activePageId ?? ""))
      ? String(source.activePageId)
      : pages[0]?.id || "",
    activeFormId: forms.some((form) => form.id === String(source.activeFormId ?? ""))
      ? String(source.activeFormId)
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

export const cleanBuilderProjectWithRepairs = (project) => {
  const normalizedProject = normalizeBuilderProjectShape(project);

  if (!normalizedProject.pages.length) {
    return repairDuplicateProjectIds(normalizedProject);
  }

  const cleanedPages = normalizedProject.pages
    .filter(
      (page, index) =>
        index === 0 ||
        !internalPageNames.has(String(page.name || "").toLowerCase())
    )
    .map((page) => {
      const baseSections = (page.sections || [])
        .filter(
          (section) =>
            !(isResponsesSection(section) && !section.isPageCanvas)
        )
        .map(removeDeprecatedBuilderElements);

      const normalizedSections = baseSections.map((section) =>
        convertSectionToDirectLayout(removeDuplicateFormHeadings(section))
      );

      return mergeSectionsIntoPageCanvas({
        ...page,
        showInNavigation: page.showInNavigation,
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

  return repairDuplicateProjectIds({
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
  });
};

export const cleanBuilderProject = (project) => cleanBuilderProjectWithRepairs(project).project;

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

export const getDraftProjectFromRecordWithRepairs = (record) => {
  if (!record?.draft_schema || typeof record.draft_schema !== "object" || Array.isArray(record.draft_schema)) {
    return { project: null, repairs: [] };
  }

  return cleanBuilderProjectWithRepairs({
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
