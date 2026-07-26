import { defaultSiteChrome, defaultTheme } from "./PageBuilder.constants";
import { normalizeProjectPageRouting } from "./PageBuilder.routing";
import { normalizeElementAction } from "./PageBuilder.actions";
import {
  stripEditorOnlyState,
  withLocalProjectEditorDefaults,
} from "./PageBuilder.editorState";
import {
  createElement,
  createColumn,
  createRow,
  createSection,
  createPage,
} from "./PageBuilder.factories";
import {
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
  let candidate;
  do {
    candidate = String(idFactory(prefix) || "").trim();
  } while (!candidate || usedIds.has(candidate));
  return candidate;
};

export const repairDuplicateProjectIds = (project, { idFactory = null } = {}) => {
  const source = project && typeof project === "object" && !Array.isArray(project)
    ? project
    : {};
  const repairs = [];
  let deterministicRepairIndex = 0;
  const nextId = idFactory || ((prefix) => `${prefix}_repaired_${++deterministicRepairIndex}`);
  const usedPageIds = new Set();
  const usedFormIds = new Set();
  const usedBlockIds = new Set();

  const repairId = ({ value, prefix, usedIds, kind, context }) => {
    const oldId = String(value ?? "").trim();
    if (oldId && !usedIds.has(oldId)) {
      usedIds.add(oldId);
      return oldId;
    }

    const newId = nextUnusedId(prefix, usedIds, nextId);
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

const deterministicRoutineId = (prefix, path) =>
  `${prefix}_${String(path || "item").replace(/[^a-z0-9]+/gi, "_").replace(/^_+|_+$/g, "").toLowerCase()}`;

const compactRichTextRanges = (ranges) => {
  if (!Array.isArray(ranges)) return [];
  const latestByTarget = new Map();
  ranges.forEach((range) => {
    if (!range || typeof range !== "object") return;
    const key = [range.field || "content", range.itemIndex ?? "", range.start ?? 0, range.end ?? 0].join(":");
    latestByTarget.set(key, range);
  });
  return [...latestByTarget.values()];
};

const normalizeBuilderElementShape = (element, path = "element") => {
  if (!element || typeof element !== "object" || Array.isArray(element)) {
    return createElement("text", { id: deterministicRoutineId("element", path) });
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
  const normalized = createElement(element.type || "text", {
    ...canonicalElement,
    id: String(element.id || deterministicRoutineId("element", path)),
  });
  normalized.id = String(normalized.id || "");
  normalized.action = normalizeElementAction(element.action);
  normalized.richTextColors = compactRichTextRanges(element.richTextColors);
  normalized.richTextSizes = compactRichTextRanges(element.richTextSizes);
  normalized.richTextStyles = compactRichTextRanges(element.richTextStyles);
  if (Array.isArray(normalized.textBlockFormats) && normalized.textBlockFormats.length) {
    let repairedContent = String(normalized.content || "");
    while (
      repairedContent.split("\n").length > normalized.textBlockFormats.length &&
      repairedContent.includes("\n\n\n")
    ) {
      repairedContent = repairedContent.replace("\n\n\n", "\n\n");
    }
    normalized.content = repairedContent;
  }
  if (
    normalized.type === "text" &&
    normalized.headingLevel &&
    Array.isArray(normalized.textBlockFormats) &&
    normalized.textBlockFormats.length > 1 &&
    normalized.textBlockFormats.every((format) => /^h[1-3]$/i.test(String(format)))
  ) {
    normalized.textBlockFormats = [normalized.textBlockFormats[0], ...normalized.textBlockFormats.slice(1).map(() => "text")];
  }
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

const normalizeBuilderColumnShape = (column, path = "column") => {
  const source =
    column && typeof column === "object" && !Array.isArray(column)
      ? column
      : {};
  const elements = Array.isArray(source.elements)
    ? source.elements.map((element, index) => normalizeBuilderElementShape(element, `${path}_element_${index}`))
    : [];

  return createColumn(elements, {
    ...source,
    id: String(source.id || deterministicRoutineId("column", path)),
    name: source.name || "Column",
    layout: {
      align: "left",
      ...(source.layout || {}),
    },
    elements,
  });
};

const normalizeBuilderRowShape = (row, path = "row") => {
  const source =
    row && typeof row === "object" && !Array.isArray(row)
      ? row
      : {};
  const columns = Array.isArray(source.columns) && source.columns.length > 0
    ? source.columns.map((column, index) => normalizeBuilderColumnShape(column, `${path}_column_${index}`))
    : [normalizeBuilderColumnShape({ elements: source.elements || [] }, `${path}_column_0`)];

  return createRow(columns, {
    ...source,
    id: String(source.id || deterministicRoutineId("row", path)),
    layout: {
      columns: String(source.layout?.columns || columns.length || 1),
      align: source.layout?.align || "center",
      gap: source.layout?.gap || "medium",
      ...(source.layout || {}),
    },
    columns,
  });
};

const normalizeBuilderSectionShape = (section, path = "section") => {
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
  const rows = Array.isArray(source.rows)
    ? source.rows.map((row, index) => normalizeBuilderRowShape(row, `${path}_row_${index}`))
    : legacyElements.length > 0 || !["direct", "free"].includes(source.mode)
      ? [normalizeBuilderRowShape({ elements: legacyElements }, `${path}_row_0`)]
      : [];
  const freeElements = sourceFreeElements.map((element, index) =>
    normalizeBuilderElementShape(element, `${path}_free_${index}`)
  );
  const canonicalSource = Object.fromEntries(
    Object.entries(source).filter(([key]) => key !== "elements")
  );

  const base = createSection({
    id: String(source.id || deterministicRoutineId("section", path)),
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

const normalizeBuilderPageShape = (page, path = "page") => {
  const source =
    page && typeof page === "object" && !Array.isArray(page)
      ? page
      : {};
  const sections = Array.isArray(source.sections)
    ? source.sections.map((section, index) => normalizeBuilderSectionShape(section, `${path}_section_${index}`))
    : [];

  const normalizedPage = createPage(source.name || "Untitled page", sections, {
    ...source,
    id: String(source.id || deterministicRoutineId("page", path)),
    slug: source.slug || source.path || "/",
    backgroundColor: source.backgroundColor || "var(--theme-surface)",
    visibility: source.visibility || "public",
    showInNavigation:
      typeof source.showInNavigation === "boolean"
        ? source.showInNavigation
        : true,
    pageType: source.pageType || "main",
    sections,
  });
  return { ...normalizedPage, id: String(normalizedPage.id || "") };
};

export const normalizeBuilderProjectShape = (project) => {
  const source =
    project && typeof project === "object" && !Array.isArray(project)
      ? project
      : {};

  const sourcePages = Array.isArray(source.pages) ? source.pages : [];
  const normalizedPages = sourcePages.map((page, index) =>
    normalizeBuilderPageShape(page, `page_${index}`)
  );
  const routedProject = normalizeProjectPageRouting({
    ...source,
    pages: normalizedPages,
  });
  const pages = routedProject.pages;

  const forms = (
    Array.isArray(source.forms)
      ? source.forms
      : []
  ).map((form, index) => ({
    ...form,
    id: String(form?.id || deterministicRoutineId("form", `form_${index}`)),
  }));

  const workflows = Array.isArray(source.workflows)
    ? source.workflows
    : [];

  const roles = Array.isArray(source.roles) ? source.roles : [];
  const users = Array.isArray(source.users) ? source.users : [];
  const collections = Array.isArray(source.collections)
    ? source.collections
    : [];

  return {
    name: "Untitled Site",
    status: "draft",
    publish: { environment: "local" },
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
      ...defaultSiteChrome,
      ...(source.siteChrome || {}),
    },
    theme: {
      ...defaultTheme,
      ...(source.theme || {}),
    },
  };
};

export const cleanBuilderProjectWithRepairs = (project) => {
  const normalizedProject = normalizeBuilderProjectShape(project);
  const layoutVersion = Number(project?.directLayoutVersion);
  const requiresExplicitLegacyLayoutMigration =
    Number.isInteger(layoutVersion) && layoutVersion > 0 && layoutVersion < 4;

  // Direct-layout conversion was a one-time, versioned migration. Routine
  // hydration/comparison must preserve modern section structures verbatim and
  // must not infer legacy content from names or block types.
  if (!requiresExplicitLegacyLayoutMigration || !normalizedProject.pages.length) {
    return repairDuplicateProjectIds(normalizedProject);
  }

  const cleanedPages = normalizedProject.pages.map((page) => {
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
  return repairDuplicateProjectIds({
    ...normalizedProject,
    directLayoutVersion: 4,
    activePageId: pages.some((page) => page.id === normalizedProject.activePageId)
      ? normalizedProject.activePageId
      : pages[0]?.id || "",
    siteChrome: normalizedProject.siteChrome,
    pages,
    forms: normalizedProject.forms,
    collections: normalizedProject.collections,
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

  return cleanValue || "builder-project";
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

  const project = cleanBuilderProject({
    ...stripEditorOnlyState(record.draft_schema),
    ...(record.status ? { status: record.status } : {}),
  });
  return withLocalProjectEditorDefaults(project);
};

export const getDraftProjectFromRecordWithRepairs = (record) => {
  if (!record?.draft_schema || typeof record.draft_schema !== "object" || Array.isArray(record.draft_schema)) {
    return { project: null, repairs: [] };
  }

  const result = cleanBuilderProjectWithRepairs({
    ...stripEditorOnlyState(record.draft_schema),
    ...(record.status ? { status: record.status } : {}),
  });
  return {
    ...result,
    project: result.project ? withLocalProjectEditorDefaults(result.project) : null,
  };
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
