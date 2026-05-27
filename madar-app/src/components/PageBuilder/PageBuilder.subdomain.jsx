import { useEffect, useMemo, useState } from "react";
import "../../styles/admin/PageBuilder/PageBuilder.css";

import {
  STORAGE_KEY,
  viewports,
  builderTabs,
  designPanels,
  sectionWidths,
  spacingOptions,
  columnOptions,
  alignmentOptions,
  elementTypes,
  fieldTypes,
  workflowStepTypes,
  defaultSiteChrome,
  starterSystems,
} from "./PageBuilder.constants";

import {
  createId,
} from "./PageBuilder.constants";

import {
  createField,
  createCollection,
  createForm,
  getFormSections,
  getFormFields,
  createElement,
  createColumn,
  createRow,
  createSection,
  createPage,
  cloneWithNewIds,
  createPosition,
} from "./PageBuilder.factories";

import {
  heroSection,
  formSection,
  responsesSection,
  loginSection,
  sectionLibrary,
  buildStarterProject,
  createInitialProject,
} from "./PageBuilder.starters";

import AuthBlock from "./AuthBlock";
import PageBuilderUsers from "./PageBuilderUsers";
import ReservationBlock from "./ReservationBlock";
import { useCurrentBuilderUser } from "./useCurrentBuilderUser";
import { getTenantLoginTarget, sanitizeSubdomain } from "./PageBuilder.routing";

const splitLines = (value) =>
  String(value || "")
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);

const getFieldType = (type) => fieldTypes.find((item) => item.id === type) || fieldTypes[0];

const reservationFieldOptions = [
  { id: "name", label: "Name" },
  { id: "contact", label: "Contact" },
  { id: "service", label: "Service" },
  { id: "date", label: "Date" },
  { id: "time", label: "Time" },
  { id: "guests", label: "Guests" },
  { id: "notes", label: "Notes" },
];

const getReservationBlockConfig = (element) => {
  const lines = splitLines(element.content);
  const reservation = element.reservation || {};

  return {
    title: reservation.title || lines[0] || "Book a reservation",
    description:
      reservation.description ||
      lines[1] ||
      "Choose a service, date, and time. We will confirm availability with you.",
    services: Array.isArray(reservation.services) && reservation.services.length > 0
      ? reservation.services
      : lines.slice(2),
    fields: Array.isArray(reservation.fields) && reservation.fields.length > 0
      ? reservation.fields
      : reservationFieldOptions.map((field) => field.id),
    submitLabel: reservation.submitLabel || "Request reservation",
  };
};

const serializeReservationBlockConfig = (config) =>
  [
    config.title,
    config.description,
    ...(config.services || []),
  ]
    .map((item) => String(item || "").trim())
    .filter(Boolean)
    .join("\n");

const getAuthBlockConfig = (element) => {
  const lines = splitLines(element.content);
  const auth = element.auth || {};
  const isRegister = element.type === "registrationBlock";
  const storedTitle = auth.title || lines[0] || "";
  const storedButtonText = auth.buttonText || lines[2] || "";
  const hasLoginCopy = ["log in", "login"].includes(storedTitle.toLowerCase()) ||
    ["log in", "login"].includes(storedButtonText.toLowerCase());
  const hasRegisterCopy = ["register", "registration"].includes(storedTitle.toLowerCase()) ||
    ["create account", "register"].includes(storedButtonText.toLowerCase());

  return {
    mode: isRegister ? "register" : "login",
    title:
      isRegister && hasLoginCopy
        ? "Register"
        : !isRegister && hasRegisterCopy
          ? "Log in"
          : storedTitle || (isRegister ? "Register" : "Log in"),
    subtitle:
      isRegister && hasLoginCopy
        ? "Create an account to save requests, reservations, and private activity."
        : !isRegister && hasRegisterCopy
          ? "Access your account and continue to your workspace."
          : auth.subtitle ||
            lines[1] ||
            (isRegister
        ? "Create an account to save requests, reservations, and private activity."
        : "Access your account and continue to your workspace."),
    buttonText:
      isRegister && hasLoginCopy
        ? "Create Account"
        : !isRegister && hasRegisterCopy
          ? "Log in"
          : storedButtonText || (isRegister ? "Create Account" : "Log in"),
    switchText:
      isRegister && hasLoginCopy
        ? "Already registered?"
        : !isRegister && hasRegisterCopy
          ? "Don't have an account?"
          : auth.switchText || (isRegister ? "Already registered?" : "Don't have an account?"),
    switchActionText:
      isRegister && hasLoginCopy
        ? "Log in"
        : !isRegister && hasRegisterCopy
          ? "Create account"
          : auth.switchActionText || (isRegister ? "Log in" : "Create account"),
  };
};

const serializeAuthBlockConfig = (config) =>
  [config.title, config.subtitle, config.buttonText]
    .map((item) => String(item || "").trim())
    .filter(Boolean)
    .join("\n");

const migrateProject = (project) => {
  const currentSiteChrome = project.siteChrome || {};
  const currentPublish = project.publish || {};

  return {
    ...project,
    siteChrome: {
      ...defaultSiteChrome,
      ...currentSiteChrome,
      headerButtonLabel:
        !currentSiteChrome.headerButtonLabel ||
        currentSiteChrome.headerButtonLabel.toLowerCase() === "contact"
          ? "Login"
          : currentSiteChrome.headerButtonLabel,
      authPageSlug: currentSiteChrome.authPageSlug || "/login",
    },
    publish: {
      environment: "local",
      subdomain: "",
      siteBaseDomain: "madar.app",
      customDomain: "",
      lastSavedAt: "",
      lastPublishedAt: "",
      ...currentPublish,
    },
  };
};

const loadInitialProject = () => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? migrateProject(JSON.parse(raw)) : migrateProject(createInitialProject());
  } catch {
    return migrateProject(createInitialProject());
  }
};

export default function PageBuilder({
  initialTab = "design",
  visibleTabIds = null,
  hideWorkspaceTabs = false,
} = {}) {
  const [project, setProject] = useState(loadInitialProject);
  const [activeTab, setActiveTab] = useState(initialTab);
  const [designPanel, setDesignPanel] = useState("Pages");
  const [viewport, setViewport] = useState("desktop");
  const [preview, setPreview] = useState(false);
  const [selected, setSelected] = useState({ type: "page", id: null });
  const [modal, setModal] = useState(null);
  const [dragState, setDragState] = useState(null);
  const [runtimeAnswers, setRuntimeAnswers] = useState({});
  const [runtimeErrors, setRuntimeErrors] = useState({});
  const [, setRuntimeReservations] = useState([]);
  const [toast, setToast] = useState("");

  useCurrentBuilderUser(setProject);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(project));
  }, [project]);

  const activePage = useMemo(
    () => project.pages.find((page) => page.id === project.activePageId) || project.pages[0],
    [project.pages, project.activePageId]
  );

  const activeForm = useMemo(
    () => project.forms.find((form) => form.id === project.activeFormId) || project.forms[0],
    [project.forms, project.activeFormId]
  );

  const activeCollection = useMemo(
    () => project.collections.find((collection) => collection.id === project.activeCollectionId) || project.collections[0],
    [project.collections, project.activeCollectionId]
  );

  const activeWorkflow = useMemo(
    () => project.workflows.find((workflow) => workflow.id === project.activeWorkflowId) || project.workflows[0],
    [project.workflows, project.activeWorkflowId]
  );

  const selectedSection = useMemo(() => {
    if (selected.type !== "section") return null;
    return activePage?.sections.find((section) => section.id === selected.id) || null;
  }, [activePage, selected]);

  const selectedColumn = useMemo(() => {
    if (selected.type !== "column") return null;

    for (const section of activePage?.sections || []) {
      for (const row of section.rows || []) {
        const column = row.columns.find((item) => item.id === selected.id);
        if (column) return column;
      }
    }

    return null;
  }, [activePage, selected]);

  const selectedElement = useMemo(() => {
    if (selected.type !== "element") return null;

    for (const section of activePage?.sections || []) {
      if (section.mode === "free") {
        const found = section.freeElements.find((item) => item.id === selected.id);
        if (found) return found;
      }

      for (const row of section.rows || []) {
        for (const column of row.columns || []) {
          const found = column.elements.find((item) => item.id === selected.id);
          if (found) return found;
        }
      }
    }

    return null;
  }, [activePage, selected]);

  const selectedRole = useMemo(() => {
    if (selected.type !== "role") return null;
    return project.roles.find((role) => role.id === selected.id) || null;
  }, [project.roles, selected]);

  const getColumnDisplayName = (columnIndex = 0, columnCount = 1) => {
    if (columnCount <= 1) return "Full width";
    if (columnCount === 2) return columnIndex === 0 ? "Left half" : "Right half";
    if (columnCount === 3) return ["Left third", "Middle third", "Right third"][columnIndex] || `Column ${columnIndex + 1}`;
    if (columnCount === 4) return `Quarter ${columnIndex + 1}`;
    return `Column ${columnIndex + 1}`;
  };

  const getColumnOptionLabel = (section, row, columnIndex, sectionIndex = 0) => {
    const rawSectionName = section?.name || "Untitled section";
    const baseSectionName = rawSectionName.replace(/\s+section$/i, "").trim() || rawSectionName;
    const friendlyNames = {
      Hero: "Hero area",
      Login: "Login form",
      Registration: "Registration form",
      Reservation: "Reservation form",
      Form: "Form area",
      Metrics: "Metrics area",
      Responses: "Responses area",
      "Responses Overview": "Responses area",
    };
    const duplicateCount = (activePage?.sections || []).filter((item) => item.name === rawSectionName).length;
    const duplicateNumber = (activePage?.sections || [])
      .slice(0, sectionIndex + 1)
      .filter((item) => item.name === rawSectionName).length;
    const sectionName = `${friendlyNames[baseSectionName] || baseSectionName}${
      duplicateCount > 1 ? ` ${duplicateNumber}` : ""
    }`;
    const rows = section?.rows || [];
    const columns = row?.columns || [];

    const columnLabel = getColumnDisplayName(columnIndex, columns.length);
    if (columns.length === 1 && rows.length === 1) {
      return sectionName;
    }

    if (rows.length <= 1) {
      return `${sectionName}: ${columnLabel}`;
    }

    return `${sectionName}: row ${rows.findIndex((item) => item.id === row.id) + 1}, ${columnLabel}`;
  };

  const getSectionLayerElements = (section) => {
    if (section.mode === "free") return section.freeElements || [];

    return (section.rows || []).flatMap((row) =>
      (row.columns || []).flatMap((column) => column.elements || [])
    );
  };

  const showToast = (message) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2200);
  };

  const updateProject = (updater) => {
    setProject((prev) => updater(prev));
  };

  const updateActivePage = (updater) => {
    updateProject((prev) => ({
      ...prev,
      pages: prev.pages.map((page) =>
        page.id === prev.activePageId ? updater(page) : page
      ),
    }));
  };

  const updateSections = (updater) => {
    updateActivePage((page) => ({ ...page, sections: updater(page.sections) }));
  };

  const updateActiveForm = (updater) => {
    updateProject((prev) => ({
      ...prev,
      forms: prev.forms.map((form) =>
        form.id === prev.activeFormId ? updater(form) : form
      ),
    }));
  };

  const updateActiveCollection = (updater) => {
    updateProject((prev) => ({
      ...prev,
      collections: prev.collections.map((collection) =>
        collection.id === prev.activeCollectionId ? updater(collection) : collection
      ),
    }));
  };

  const updateActiveWorkflow = (updater) => {
    updateProject((prev) => ({
      ...prev,
      workflows: prev.workflows.map((workflow) =>
        workflow.id === prev.activeWorkflowId ? updater(workflow) : workflow
      ),
    }));
  };

  const selectPage = (pageId) => {
    updateProject((prev) => ({ ...prev, activePageId: pageId }));
    setSelected({ type: "page", id: pageId });
  };

  const selectForm = (formId) => {
    updateProject((prev) => ({ ...prev, activeFormId: formId }));
    setSelected({ type: "form", id: formId });
  };

  const selectCollection = (collectionId) => {
    updateProject((prev) => ({ ...prev, activeCollectionId: collectionId }));
    setSelected({ type: "collection", id: collectionId });
  };

  const selectWorkflow = (workflowId) => {
    updateProject((prev) => ({ ...prev, activeWorkflowId: workflowId }));
    setSelected({ type: "workflow", id: workflowId });
  };

  const addPage = () => {
    const page = createPage(`Page ${project.pages.length + 1}`, [heroSection()]);
    updateProject((prev) => ({
      ...prev,
      pages: [...prev.pages, page],
      activePageId: page.id,
    }));
    setSelected({ type: "page", id: page.id });
  };

  const duplicatePage = () => {
    if (!activePage) return;
    const copy = cloneWithNewIds(activePage);
    copy.name = `${activePage.name} Copy`;
    copy.slug = `${activePage.slug === "/" ? "/home" : activePage.slug}-copy`;

    updateProject((prev) => ({
      ...prev,
      pages: [...prev.pages, copy],
      activePageId: copy.id,
    }));

    setSelected({ type: "page", id: copy.id });
  };

  const deleteActivePage = () => {
    if (!activePage || project.pages.length <= 1) {
      alert("You need at least one page.");
      return;
    }

    if (!window.confirm(`Delete page "${activePage.name}"?`)) return;

    const nextPage = project.pages.find((page) => page.id !== activePage.id);
    updateProject((prev) => ({
      ...prev,
      pages: prev.pages.filter((page) => page.id !== activePage.id),
      activePageId: nextPage.id,
    }));
    setSelected({ type: "page", id: nextPage.id });
  };

  const addSection = (factory) => {
    const section = factory(project.activeFormId);
    updateSections((sections) => [...sections, section]);
    setSelected({ type: "section", id: section.id });
    setModal(null);
  };

  const duplicateSelectedSection = () => {
    if (!selectedSection) return;
    const copy = cloneWithNewIds(selectedSection);
    copy.name = `${selectedSection.name} Copy`;

    updateSections((sections) => {
      const index = sections.findIndex((item) => item.id === selectedSection.id);
      const next = [...sections];
      next.splice(index + 1, 0, copy);
      return next;
    });

    setSelected({ type: "section", id: copy.id });
  };

  const updateSelectedSection = (updates) => {
    if (!selectedSection) return;

    updateSections((sections) =>
      sections.map((section) =>
        section.id === selectedSection.id
          ? {
              ...section,
              ...updates,
              layout: { ...section.layout, ...(updates.layout || {}) },
            }
          : section
      )
    );
  };

  const deleteSelectedSection = () => {
    if (!selectedSection) return;
    if (!window.confirm(`Delete section "${selectedSection.name}"?`)) return;

    updateSections((sections) => sections.filter((section) => section.id !== selectedSection.id));
    setSelected({ type: "page", id: activePage.id });
  };

  const addRowToSelectedSection = () => {
    if (!selectedSection || selectedSection.mode !== "auto") return;

    const row = createRow([createColumn()]);
    updateSections((sections) =>
      sections.map((section) =>
        section.id === selectedSection.id
          ? { ...section, rows: [...(section.rows || []), row] }
          : section
      )
    );
  };

  const updateSectionRow = (rowId, updates) => {
    if (!selectedSection) return;

    updateSections((sections) =>
      sections.map((section) =>
        section.id === selectedSection.id
          ? {
              ...section,
              rows: section.rows.map((row) =>
                row.id === rowId
                  ? { ...row, ...updates, layout: { ...row.layout, ...(updates.layout || {}) } }
                  : row
              ),
            }
          : section
      )
    );
  };

  const setRowColumnCount = (rowId, count) => {
    if (!selectedSection) return;

    updateSections((sections) =>
      sections.map((section) => {
        if (section.id !== selectedSection.id) return section;

        return {
          ...section,
          rows: section.rows.map((row) => {
            if (row.id !== rowId) return row;

            const nextColumns = [...row.columns];
            while (nextColumns.length < count) nextColumns.push(createColumn());
            const trimmedColumns = nextColumns.slice(0, count);
            const overflowColumns = nextColumns.slice(count);
            const overflowElements = overflowColumns.flatMap((column) => column.elements || []);

            if (overflowElements.length > 0 && trimmedColumns.length > 0) {
              trimmedColumns[trimmedColumns.length - 1] = {
                ...trimmedColumns[trimmedColumns.length - 1],
                elements: [
                  ...(trimmedColumns[trimmedColumns.length - 1].elements || []),
                  ...overflowElements,
                ],
              };
            }

            return {
              ...row,
              layout: { ...row.layout, columns: String(count) },
              columns: trimmedColumns,
            };
          }),
        };
      })
    );
  };

  const duplicateSectionRow = (rowId) => {
    if (!selectedSection) return;
    const sourceRow = selectedSection.rows.find((row) => row.id === rowId);
    if (!sourceRow) return;

    const copy = cloneWithNewIds(sourceRow);
    updateSections((sections) =>
      sections.map((section) => {
        if (section.id !== selectedSection.id) return section;
        const index = section.rows.findIndex((row) => row.id === rowId);
        const rows = [...section.rows];
        rows.splice(index + 1, 0, copy);
        return { ...section, rows };
      })
    );
  };

  const deleteSectionRow = (rowId) => {
    if (!selectedSection || selectedSection.rows.length <= 1) return;

    updateSections((sections) =>
      sections.map((section) =>
        section.id === selectedSection.id
          ? { ...section, rows: section.rows.filter((row) => row.id !== rowId) }
          : section
      )
    );
  };

  const updateSelectedColumn = (updates) => {
    if (!selectedColumn) return;

    updateSections((sections) =>
      sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
          ...row,
          columns: row.columns.map((column) =>
            column.id === selectedColumn.id
              ? { ...column, ...updates, layout: { ...column.layout, ...(updates.layout || {}) } }
              : column
          ),
        })),
      }))
    );
  };

  const smartAddElement = (type) => {
    const element = createElement(type, type === "formBlock" || type === "responsesTable" ? { connectedFormId: project.activeFormId } : {});

    if (type === "loginBlock" || type === "registrationBlock") {
      const section = createSection({
        name: type === "registrationBlock" ? "Registration Section" : "Login Section",
        layout: { width: "medium", paddingY: "large", background: "#fbfaf8" },
        rows: [createRow([createColumn([element])])],
      });

      updateSections((sections) => [...sections, section]);
      setSelected({ type: "element", id: element.id });
      return;
    }

    if (type === "reservationBlock") {
      const section = createSection({
        name: "Reservation Section",
        layout: { width: "full", paddingY: "medium" },
        rows: [createRow([createColumn([element])])],
      });

      updateSections((sections) => [...sections, section]);
      setSelected({ type: "element", id: element.id });
      return;
    }

    if (selectedSection?.mode === "free") {
      updateSections((sections) =>
        sections.map((section) =>
          section.id === selectedSection.id
            ? { ...section, freeElements: [...section.freeElements, { ...element, mode: "free" }] }
            : section
        )
      );
      setSelected({ type: "element", id: element.id });
      return;
    }

    let targetColumnId = selectedColumn?.id;

    if (!targetColumnId && selectedSection?.mode === "auto") {
      targetColumnId = selectedSection.rows?.[0]?.columns?.[0]?.id;
    }

    if (!targetColumnId) {
      const latestSection = activePage.sections[activePage.sections.length - 1];
      targetColumnId = latestSection?.rows?.[0]?.columns?.[0]?.id;
    }

    if (!targetColumnId) {
      const section = createSection({
        name: "Quick Section",
        rows: [createRow([createColumn([element])])],
      });
      updateSections((sections) => [...sections, section]);
      setSelected({ type: "element", id: element.id });
      return;
    }

    updateSections((sections) =>
      sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
          ...row,
          columns: row.columns.map((column) =>
            column.id === targetColumnId
              ? { ...column, elements: [...column.elements, element] }
              : column
          ),
        })),
      }))
    );

    setSelected({ type: "element", id: element.id });
  };

  const updateSelectedElement = (updates) => {
    if (!selectedElement) return;

    const merge = (element) => ({
      ...element,
      ...updates,
      styles: { ...element.styles, ...(updates.styles || {}) },
      action: { ...element.action, ...(updates.action || {}) },
    });

    updateSections((sections) =>
      sections.map((section) => {
        if (section.mode === "free") {
          return {
            ...section,
            freeElements: section.freeElements.map((element) =>
              element.id === selectedElement.id ? merge(element) : element
            ),
          };
        }

        return {
          ...section,
          rows: section.rows.map((row) => ({
            ...row,
            columns: row.columns.map((column) => ({
              ...column,
              elements: column.elements.map((element) =>
                element.id === selectedElement.id ? merge(element) : element
              ),
            })),
          })),
        };
      })
    );
  };

  const updateSelectedReservationBlock = (updates) => {
    if (!selectedElement || selectedElement.type !== "reservationBlock") return;

    const nextConfig = {
      ...getReservationBlockConfig(selectedElement),
      ...updates,
    };

    updateSelectedElement({
      reservation: nextConfig,
      content: serializeReservationBlockConfig(nextConfig),
    });
  };

  const updateSelectedAuthBlock = (updates) => {
    if (!selectedElement || !["loginBlock", "registrationBlock"].includes(selectedElement.type)) return;

    const nextConfig = {
      ...getAuthBlockConfig(selectedElement),
      ...updates,
    };

    updateSelectedElement({
      auth: nextConfig,
      content: serializeAuthBlockConfig(nextConfig),
    });
  };

  const moveSelectedReservationToWideSection = () => {
    if (!selectedElement || selectedElement.type !== "reservationBlock") return;

    const elementToMove = { ...selectedElement, mode: "auto" };
    const section = createSection({
      name: "Reservation Section",
      layout: { width: "full", paddingY: "medium" },
      rows: [createRow([createColumn([elementToMove])])],
    });

    updateSections((sections) => {
      const cleanedSections = sections
        .map((item) => {
          if (item.mode === "free") {
            return {
              ...item,
              freeElements: item.freeElements.filter((element) => element.id !== selectedElement.id),
            };
          }

          return {
            ...item,
            rows: item.rows
              .map((row) => ({
                ...row,
                columns: row.columns.map((column) => ({
                  ...column,
                  elements: column.elements.filter((element) => element.id !== selectedElement.id),
                })),
              }))
              .filter((row) => row.columns.some((column) => column.elements.length > 0)),
          };
        })
        .filter((item) => item.mode === "free" || item.rows.length > 0);

      return [...cleanedSections, section];
    });

    setSelected({ type: "element", id: selectedElement.id });
    showToast("Reservation moved to a wide section.");
  };

  const deleteSelectedElement = () => {
    if (!selectedElement) return;
    if (!window.confirm(`Delete "${selectedElement.name}"?`)) return;

    updateSections((sections) =>
      sections.map((section) => {
        if (section.mode === "free") {
          return {
            ...section,
            freeElements: section.freeElements.filter((element) => element.id !== selectedElement.id),
          };
        }

        return {
          ...section,
          rows: section.rows.map((row) => ({
            ...row,
            columns: row.columns.map((column) => ({
              ...column,
              elements: column.elements.filter((element) => element.id !== selectedElement.id),
            })),
          })),
        };
      })
    );

    setSelected({ type: "page", id: activePage.id });
  };

  const findElementLocation = (elementId) => {
    for (const section of activePage?.sections || []) {
      if (section.mode === "free") {
        const elementIndex = section.freeElements.findIndex((element) => element.id === elementId);
        if (elementIndex >= 0) return { sectionId: section.id, elementIndex, isFree: true };
      }

      for (const row of section.rows || []) {
        for (const column of row.columns || []) {
          const elementIndex = column.elements.findIndex((element) => element.id === elementId);
          if (elementIndex >= 0) {
            return { sectionId: section.id, rowId: row.id, columnId: column.id, elementIndex, isFree: false };
          }
        }
      }
    }

    return null;
  };

  const duplicateSelectedElement = () => {
    if (!selectedElement) return;
    const location = findElementLocation(selectedElement.id);
    const copy = cloneWithNewIds(selectedElement);
    copy.name = `${selectedElement.name} Copy`;

    updateSections((sections) =>
      sections.map((section) => {
        if (section.id !== location?.sectionId) return section;

        if (location.isFree) {
          const freeElements = [...section.freeElements];
          freeElements.splice(location.elementIndex + 1, 0, copy);
          return { ...section, freeElements };
        }

        return {
          ...section,
          rows: section.rows.map((row) => ({
            ...row,
            columns: row.columns.map((column) => {
              if (column.id !== location.columnId) return column;
              const elements = [...column.elements];
              elements.splice(location.elementIndex + 1, 0, copy);
              return { ...column, elements };
            }),
          })),
        };
      })
    );

    setSelected({ type: "element", id: copy.id });
  };

  const moveSelectedElement = (direction) => {
    if (!selectedElement) return;
    const location = findElementLocation(selectedElement.id);
    if (!location || location.isFree) return;

    updateSections((sections) =>
      sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
          ...row,
          columns: row.columns.map((column) => {
            if (column.id !== location.columnId) return column;
            const elements = [...column.elements];
            const targetIndex = direction === "up" ? location.elementIndex - 1 : location.elementIndex + 1;
            if (targetIndex < 0 || targetIndex >= elements.length) return column;
            [elements[location.elementIndex], elements[targetIndex]] = [elements[targetIndex], elements[location.elementIndex]];
            return { ...column, elements };
          }),
        })),
      }))
    );
  };

  const moveSelectedElementToColumn = (columnId) => {
    if (!selectedElement) return;
    const location = findElementLocation(selectedElement.id);
    if (!location || location.isFree || location.columnId === columnId) return;

    updateSections((sections) =>
      sections.map((section) => ({
        ...section,
        rows: section.rows.map((row) => ({
          ...row,
          columns: row.columns.map((column) => {
            if (column.id === location.columnId) {
              return {
                ...column,
                elements: column.elements.filter((element) => element.id !== selectedElement.id),
              };
            }

            if (column.id === columnId) {
              return { ...column, elements: [...column.elements, selectedElement] };
            }

            return column;
          }),
        })),
      }))
    );
  };

  const getFreePositionBasis = (key) => {
    if (key === "x" || key === "width") return viewports[viewport] || viewports.desktop;

    const location = selectedElement ? findElementLocation(selectedElement.id) : null;
    const section = activePage?.sections.find((item) => item.id === location?.sectionId);
    return section?.layout?.minHeight || 560;
  };

  const getElementPositionPercent = (key) => {
    if (!selectedElement) return 0;

    const current = selectedElement.position?.[viewport] || createPosition()[viewport];
    const value = Number(current[key] || 0);
    const basis = getFreePositionBasis(key);
    return Math.round((value / basis) * 100);
  };

  const updateElementPositionPercent = (key, value) => {
    if (!selectedElement) return;

    const percent = value === "" ? "" : Number(value);
    const basis = getFreePositionBasis(key);
    const nextValue = percent === "" ? "" : Math.round((basis * percent) / 100);
    updateElementPosition(key, nextValue);
  };

  const updateElementPosition = (key, value) => {
    if (!selectedElement) return;

    const current = selectedElement.position?.[viewport] || createPosition()[viewport];
    const nextValue = value === "" ? "" : Number(value);

    updateSelectedElement({
      position: {
        ...selectedElement.position,
        [viewport]: {
          ...current,
          [key]: nextValue,
        },
      },
    });
  };

  const uploadImageForSelectedElement = (file) => {
    if (!file || !selectedElement || selectedElement.type !== "image") return;

    if (!file.type.startsWith("image/")) {
      alert("Please choose an image file.");
      return;
    }

    const reader = new FileReader();

    reader.onload = () => {
      updateSelectedElement({
        content: reader.result,
        name: selectedElement.name || file.name,
      });
    };

    reader.onerror = () => {
      alert("Could not read this image. Please try another file.");
    };

    reader.readAsDataURL(file);
  };

  const uploadSiteLogo = (file) => {
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("Please choose an image file.");
      return;
    }

    const reader = new FileReader();

    reader.onload = () => {
      updateProject((prev) => ({
        ...prev,
        siteChrome: {
          ...(prev.siteChrome || defaultSiteChrome),
          logoUrl: reader.result,
        },
      }));
    };

    reader.onerror = () => alert("Could not read this logo. Please try another file.");
    reader.readAsDataURL(file);
  };

  const addCollection = () => {
    const collection = createCollection(`Collection ${project.collections.length + 1}`);
    updateProject((prev) => ({
      ...prev,
      collections: [...prev.collections, collection],
      activeCollectionId: collection.id,
    }));
    setSelected({ type: "collection", id: collection.id });
  };

  const addFieldToCollection = () => {
    const field = createField(`Field ${activeCollection.fields.length + 1}`);
    updateActiveCollection((collection) => ({
      ...collection,
      fields: [...collection.fields, field],
    }));
  };

  const updateCollectionField = (fieldId, updates) => {
    updateActiveCollection((collection) => ({
      ...collection,
      fields: collection.fields.map((field) =>
        field.id === fieldId ? { ...field, ...updates } : field
      ),
    }));
  };

  const deleteCollectionField = (fieldId) => {
    updateActiveCollection((collection) => ({
      ...collection,
      fields: collection.fields.filter((field) => field.id !== fieldId),
    }));
  };

  const addForm = () => {
    const form = createForm(`Form ${project.forms.length + 1}`, [createField("Question 1", "shortText")]);
    updateProject((prev) => ({
      ...prev,
      forms: [...prev.forms, form],
      activeFormId: form.id,
      workflows: [...prev.workflows, createWorkflow(`After ${form.title} is submitted`, form.id)],
    }));
    setSelected({ type: "form", id: form.id });
  };

  const addFormSection = () => {
    const section = {
      id: createId("formSection"),
      title: `Section ${getFormSections(activeForm).length + 1}`,
      description: "",
      collapsed: false,
      fields: [],
    };

    updateActiveForm((form) => ({
      ...form,
      sections: [...getFormSections(form), section],
    }));
  };

  const addFieldToForm = (type = "shortText", sectionId = null) => {
    if (!activeForm) return;
    const meta = getFieldType(type);
    const field = createField(meta.label, type);
    const targetSectionId = sectionId || getFormSections(activeForm)[0]?.id;

    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) =>
        section.id === targetSectionId
          ? { ...section, fields: [...(section.fields || []), field] }
          : section
      ),
    }));

    setSelected({ type: "field", id: field.id });
  };

  const updateFormField = (fieldId, updates) => {
    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) => ({
        ...section,
        fields: (section.fields || []).map((field) =>
          field.id === fieldId ? { ...field, ...updates } : field
        ),
      })),
    }));
  };

  const updateFormSection = (sectionId, updates) => {
    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) =>
        section.id === sectionId ? { ...section, ...updates } : section
      ),
    }));
  };

  const duplicateFormField = (fieldId) => {
    if (!activeForm) return;
    let nextFieldId = "";

    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) => {
        const fieldIndex = (section.fields || []).findIndex((field) => field.id === fieldId);
        if (fieldIndex < 0) return section;

        const copy = cloneWithNewIds(section.fields[fieldIndex]);
        copy.label = `${section.fields[fieldIndex].label} Copy`;
        nextFieldId = copy.id;
        const fields = [...section.fields];
        fields.splice(fieldIndex + 1, 0, copy);
        return { ...section, fields };
      }),
    }));

    if (nextFieldId) setSelected({ type: "field", id: nextFieldId });
  };

  const moveFormField = (fieldId, direction) => {
    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) => {
        const fieldIndex = (section.fields || []).findIndex((field) => field.id === fieldId);
        if (fieldIndex < 0) return section;

        const targetIndex = direction === "up" ? fieldIndex - 1 : fieldIndex + 1;
        if (targetIndex < 0 || targetIndex >= section.fields.length) return section;

        const fields = [...section.fields];
        [fields[fieldIndex], fields[targetIndex]] = [fields[targetIndex], fields[fieldIndex]];
        return { ...section, fields };
      }),
    }));
  };

  const deleteFormSection = (sectionId) => {
    if (!activeForm || getFormSections(activeForm).length <= 1) return;

    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).filter((section) => section.id !== sectionId),
    }));
  };

  const deleteFormField = (fieldId) => {
    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) => ({
        ...section,
        fields: (section.fields || []).filter((field) => field.id !== fieldId),
      })),
    }));
    setSelected({ type: "form", id: activeForm?.id });
  };

  const addWorkflow = () => {
    const workflow = createWorkflow(`Workflow ${project.workflows.length + 1}`, project.activeFormId);
    updateProject((prev) => ({
      ...prev,
      workflows: [...prev.workflows, workflow],
      activeWorkflowId: workflow.id,
    }));
    setSelected({ type: "workflow", id: workflow.id });
  };

  const addWorkflowStep = () => {
    const step = {
      id: createId("workflowStep"),
      type: "showMessage",
      label: "New step",
      details: "Describe what this step should do later.",
    };

    updateActiveWorkflow((workflow) => ({
      ...workflow,
      steps: [...workflow.steps, step],
    }));
  };

  const updateWorkflowStep = (stepId, updates) => {
    updateActiveWorkflow((workflow) => ({
      ...workflow,
      steps: workflow.steps.map((step) =>
        step.id === stepId ? { ...step, ...updates } : step
      ),
    }));
  };

  const deleteWorkflowStep = (stepId) => {
    updateActiveWorkflow((workflow) => ({
      ...workflow,
      steps: workflow.steps.filter((step) => step.id !== stepId),
    }));
  };

  const setAnswer = (formId, fieldId, value) => {
    setRuntimeAnswers((prev) => ({
      ...prev,
      [formId]: {
        ...(prev[formId] || {}),
        [fieldId]: value,
      },
    }));

    setRuntimeErrors((prev) => {
      const next = { ...prev };
      delete next[fieldId];
      return next;
    });
  };

  const submitRuntimeForm = (form) => {
    const answers = runtimeAnswers[form.id] || {};
    const nextErrors = {};

    getFormFields(form).forEach((field) => {
      if (!field.required) return;
      const value = answers[field.id];

      if (
        value === undefined ||
        value === null ||
        value === "" ||
        (Array.isArray(value) && value.length === 0)
      ) {
        nextErrors[field.id] = "This field is required.";
      }
    });

    setRuntimeErrors(nextErrors);

    if (Object.keys(nextErrors).length > 0) return;

    const response = {
      id: createId("response"),
      createdAt: new Date().toISOString(),
      status: "New",
      answers,
    };

    updateProject((prev) => ({
      ...prev,
      forms: prev.forms.map((item) =>
        item.id === form.id ? { ...item, responses: [response, ...item.responses] } : item
      ),
      collections: prev.collections.map((collection) =>
        collection.id === form.connectedCollectionId
          ? { ...collection, records: [response, ...(collection.records || [])] }
          : collection
      ),
    }));

    setRuntimeAnswers((prev) => ({ ...prev, [form.id]: {} }));
    showToast(form.successMessage);
  };

  const submitRuntimeReservation = (elementId, reservation) => {
    setRuntimeReservations((prev) => [
      {
        id: createId("reservation"),
        elementId,
        ...reservation,
      },
      ...prev,
    ]);

    showToast("Reservation request submitted.");
  };

  const runElementAction = (element) => {
    const action = element.action || {};

    if (action.type === "goToPage" && action.pageId) {
      selectPage(action.pageId);
      return;
    }

    if (action.type === "openUrl" && action.url) {
      window.open(action.url, "_blank", "noopener,noreferrer");
      return;
    }

    if (action.type === "showMessage" && action.message) {
      showToast(action.message);
    }
  };

  const updatePublishSettings = (updates) => {
    updateProject((prev) => ({
      ...prev,
      publish: {
        ...(prev.publish || {}),
        ...updates,
      },
    }));
  };

  const saveProject = () => {
    const nextProject = {
      ...project,
      publish: {
        ...project.publish,
        lastSavedAt: new Date().toISOString(),
      },
    };

    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextProject));
    setProject(nextProject);
    showToast("Saved locally.");
  };

  const loadProject = () => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      alert("No saved project found.");
      return;
    }

    try {
      const loaded = JSON.parse(raw);
      setProject(loaded);
      setSelected({ type: "page", id: loaded.activePageId });
      showToast("Loaded saved project.");
    } catch {
      alert("Saved project is not valid JSON.");
    }
  };

  const publishProject = () => {
    updateProject((prev) => ({
      ...prev,
      status: "published",
      publish: {
        ...prev.publish,
        lastPublishedAt: new Date().toISOString(),
      },
    }));

    showToast("Published locally. Backend connection comes later.");
  };

  const exportProject = () => {
    const payload = JSON.stringify(project, null, 2);
    console.log(payload);

    try {
      navigator.clipboard.writeText(payload);
      showToast("Exported JSON copied to clipboard.");
    } catch {
      showToast("Exported JSON printed to console.");
    }
  };

  const applyStarter = (starterId) => {
    const starter = buildStarterProject(starterId);
    setProject(starter);
    setSelected({ type: "page", id: starter.activePageId });
    setActiveTab("design");
    setModal(null);
  };

  const getFormPlacements = (formId) =>
    project.pages.flatMap((page) =>
      page.sections.flatMap((section) => {
        const autoElements = (section.rows || []).flatMap((row) =>
          (row.columns || []).flatMap((column) => column.elements || [])
        );
        const freeElements = section.freeElements || [];
        const connected = [...autoElements, ...freeElements].some(
          (element) =>
            ["formBlock", "responsesTable"].includes(element.type) &&
            element.connectedFormId === formId
        );

        return connected ? [{ pageId: page.id, pageName: page.name, sectionName: section.name }] : [];
      })
    );

  const addConnectedFormSectionToPage = (formId, pageId = project.activePageId) => {
    if (!formId || !pageId) return;

    const section = formSection(formId);

    updateProject((prev) => ({
      ...prev,
      activePageId: pageId,
      activeFormId: formId,
      pages: prev.pages.map((page) =>
        page.id === pageId ? { ...page, sections: [...page.sections, section] } : page
      ),
    }));

    setSelected({ type: "section", id: section.id });
    setActiveTab("design");
    setDesignPanel("Layers");
    showToast("Form added to the selected page.");
  };

  const addConnectedResponsesSectionToPage = (formId, pageId = project.activePageId) => {
    if (!formId || !pageId) return;

    const section = responsesSection(formId);

    updateProject((prev) => ({
      ...prev,
      activePageId: pageId,
      activeFormId: formId,
      pages: prev.pages.map((page) =>
        page.id === pageId ? { ...page, sections: [...page.sections, section] } : page
      ),
    }));

    setSelected({ type: "section", id: section.id });
    setActiveTab("design");
    setDesignPanel("Layers");
    showToast("Responses table added to the selected page.");
  };

  const getElementStyle = (element) => {
    const isSelected = selected.type === "element" && selected.id === element.id;

    return {
      ...element.styles,
      position: "relative",
      transform: undefined,
      width: element.styles.width || undefined,
      minHeight: undefined,
      maxWidth: "100%",
      alignSelf:
        element.styles.alignSelf === "auto" ? undefined : element.styles.alignSelf,
      zIndex: isSelected ? 5 : 1,
    };
  };

  const getFreeElementStyle = (element) => {
    const pos = element.position?.[viewport] || createPosition()[viewport];

    return {
      ...element.styles,
      position: "absolute",
      left: `${pos.x}px`,
      top: `${pos.y}px`,
      width: `${pos.width}px`,
      minHeight: `${pos.height}px`,
    };
  };

  const startDrag = (event, element) => {
    if (preview || element.mode !== "free") return;

    const tagName = event.target?.tagName?.toLowerCase();
    if (["input", "textarea", "select", "option", "button"].includes(tagName)) return;

    event.stopPropagation();
    event.preventDefault();

    const current = element.position?.[viewport] || createPosition()[viewport];

    setSelected({ type: "element", id: element.id });
    setDragState({
      elementId: element.id,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startX: current.x || 0,
      startY: current.y || 0,
    });
  };

  const handleMouseMove = (event) => {
    if (!dragState || !selectedElement || selectedElement.id !== dragState.elementId) return;

    const current = selectedElement.position?.[viewport] || createPosition()[viewport];
    const deltaX = event.clientX - dragState.startClientX;
    const deltaY = event.clientY - dragState.startClientY;

    updateSelectedElement({
      position: {
        ...selectedElement.position,
        [viewport]: {
          ...current,
          x: Math.max(-600, dragState.startX + deltaX),
          y: Math.max(-600, dragState.startY + deltaY),
        },
      },
    });
  };

  const renderFieldInput = (form, field, disabled = false) => {
    const value = runtimeAnswers[form.id]?.[field.id] || "";
    const error = runtimeErrors[field.id];
    const meta = getFieldType(field.type);

    const common = {
      disabled,
      value,
      onChange: (event) => setAnswer(form.id, field.id, event.target.value),
    };

    let inputNode = null;

    if (["text", "email", "tel", "number", "date"].includes(meta.input)) {
      inputNode = <input type={meta.input} placeholder={field.placeholder} {...common} />;
    } else if (meta.input === "textarea") {
      inputNode = <textarea placeholder={field.placeholder} {...common} />;
    } else if (meta.input === "select") {
      inputNode = (
        <select {...common}>
          <option value="">Choose...</option>
          {field.options.map((option) => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
      );
    } else if (meta.input === "radio") {
      inputNode = (
        <div className="choice-list">
          {field.options.map((option) => (
            <label key={option}>
              <input
                type="radio"
                name={field.id}
                checked={value === option}
                disabled={disabled}
                onChange={() => setAnswer(form.id, field.id, option)}
              />
              <span>{option}</span>
            </label>
          ))}
        </div>
      );
    } else if (meta.input === "checkboxes") {
      const values = Array.isArray(runtimeAnswers[form.id]?.[field.id])
        ? runtimeAnswers[form.id][field.id]
        : [];

      inputNode = (
        <div className="choice-list">
          {field.options.map((option) => (
            <label key={option}>
              <input
                type="checkbox"
                checked={values.includes(option)}
                disabled={disabled}
                onChange={(event) => {
                  const next = event.target.checked
                    ? [...values, option]
                    : values.filter((item) => item !== option);
                  setAnswer(form.id, field.id, next);
                }}
              />
              <span>{option}</span>
            </label>
          ))}
        </div>
      );
    } else if (meta.input === "yesNo") {
      inputNode = (
        <div className="choice-pills">
          {["Yes", "No"].map((option) => (
            <button
              type="button"
              key={option}
              disabled={disabled}
              className={value === option ? "active" : ""}
              onClick={() => setAnswer(form.id, field.id, option)}
            >
              {option}
            </button>
          ))}
        </div>
      );
    } else if (meta.input === "file") {
      inputNode = <input type="file" disabled={disabled} />;
    }

    return (
      <div className={`runtime-question ${error ? "has-error" : ""}`} key={field.id}>
        <label>
          <span>
            {field.label}
            {field.required ? " *" : ""}
          </span>
          {field.helpText && <small>{field.helpText}</small>}
          {inputNode}
          {error && <strong>{error}</strong>}
        </label>
      </div>
    );
  };

  const renderConnectedForm = (formId) => {
    const form = project.forms.find((item) => item.id === formId) || project.forms[0];
    if (!form) return <div className="empty-connected">No form selected.</div>;

    return (
      <div className="runtime-form">
        <div className="runtime-form-header">
          <h3>{form.title}</h3>
          <p>{form.description}</p>
        </div>

        {getFormSections(form).map((section) => (
          <div className="runtime-form-section" key={section.id}>
            <div className="runtime-form-section-header">
              <h4>{section.title}</h4>
              {section.description && <p>{section.description}</p>}
            </div>

            {(section.fields || []).map((field) => renderFieldInput(form, field, !preview))}
          </div>
        ))}

        <button
          type="button"
          className="runtime-submit"
          disabled={!preview}
          onClick={() => submitRuntimeForm(form)}
        >
          Submit
        </button>

        {!preview && <p className="builder-note">Enable Preview to test this form.</p>}
      </div>
    );
  };

  const renderResponsesTable = (formId) => {
    const form = project.forms.find((item) => item.id === formId) || project.forms[0];
    if (!form) return <div className="empty-connected">No form selected.</div>;

    const fields = getFormFields(form).slice(0, 4);
    const responses = form.responses;

    return (
      <div className="responses-preview">
        <div className="responses-preview-header">
          <strong>{form.title}</strong>
          <span>{responses.length} responses</span>
        </div>

        <div className="mock-table">
          <div className="mock-table-row mock-table-head">
            <span>Status</span>
            {fields.map((field) => (
              <span key={field.id}>{field.label}</span>
            ))}
          </div>

          {(responses.length ? responses : [{ id: "sample", status: "Sample", answers: {} }]).map((response) => (
            <div className="mock-table-row" key={response.id}>
              <span>{response.status || "New"}</span>
              {fields.map((field) => (
                <span key={field.id}>{response.answers?.[field.id] || "—"}</span>
              ))}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderElement = (element, isFree = false) => {
    const isSelected = selected.type === "element" && selected.id === element.id;

    const commonProps = {
      className: `builder-element builder-element-${element.type} ${isSelected ? "is-selected" : ""}`,
      style: isFree ? getFreeElementStyle(element) : getElementStyle(element),
      onMouseDown: (event) => startDrag(event, element),
      onClick: (event) => {
        event.stopPropagation();
        if (!preview) setSelected({ type: "element", id: element.id });
      },
    };

    if (element.type === "heading") {
      return <h1 key={element.id} {...commonProps}>{element.content}</h1>;
    }

    if (element.type === "text") {
      return <p key={element.id} {...commonProps}>{element.content}</p>;
    }

    if (element.type === "button") {
      return (
        <button
          key={element.id}
          type="button"
          {...commonProps}
          onClick={(event) => {
            commonProps.onClick(event);
            if (preview) runElementAction(element);
          }}
        >
          {element.content}
        </button>
      );
    }

    if (element.type === "image") {
      return <img key={element.id} {...commonProps} src={element.content} alt={element.name} />;
    }

    if (element.type === "card") {
      return (
        <div key={element.id} {...commonProps}>
          {String(element.content || "").split("\n").map((line, index) => (
            <span key={`${element.id}_${index}`}>{line}</span>
          ))}
        </div>
      );
    }

    if (element.type === "list") {
      return (
        <ul key={element.id} {...commonProps}>
          {splitLines(element.content).map((item) => <li key={item}>{item}</li>)}
        </ul>
      );
    }

    if (element.type === "divider") {
      return <hr key={element.id} {...commonProps} />;
    }

    if (element.type === "embed") {
      return (
        <div key={element.id} {...commonProps}>
          <strong>Embed</strong>
          <a href={element.content} target="_blank" rel="noreferrer">{element.content}</a>
        </div>
      );
    }

    if (element.type === "metric") {
      const [label, value] = String(element.content || "").split("\n");
      return (
        <div key={element.id} {...commonProps}>
          <span className="metric-label">{label}</span>
          <strong className="metric-value">{value}</strong>
        </div>
      );
    }

    if (element.type === "formBlock") {
      return <div key={element.id} {...commonProps}>{renderConnectedForm(element.connectedFormId)}</div>;
    }

    if (element.type === "loginBlock" || element.type === "registrationBlock") {
      const authConfig = getAuthBlockConfig(element);

      return (
        <div key={element.id} {...commonProps}>
          <AuthBlock
            {...authConfig}
            disabled={!preview}
            onLogin={() => showToast("Logged in. Redirecting to the login workspace.")}
            onRegister={() => showToast("Account created. Please log in.")}
          />
        </div>
      );
    }

    if (element.type === "reservationBlock") {
      const reservationConfig = getReservationBlockConfig(element);

      return (
        <div key={element.id} {...commonProps}>
          <ReservationBlock
            {...reservationConfig}
            disabled={!preview}
            submitLabel={reservationConfig.submitLabel}
            onSubmit={(reservation) => submitRuntimeReservation(element.id, reservation)}
          />
        </div>
      );
    }

    if (element.type === "responsesTable") {
      return <div key={element.id} {...commonProps}>{renderResponsesTable(element.connectedFormId)}</div>;
    }

    return <div key={element.id} {...commonProps}>{element.content}</div>;
  };

  const openOrCreateLoginPage = () => {
    const site = project.siteChrome || defaultSiteChrome;
    const targetSlug = site.authPageSlug || "/login";

    const existingLoginPage = project.pages.find((page) => {
      const pageName = String(page.name || "").toLowerCase().trim();
      const pageSlug = String(page.slug || "").toLowerCase().trim();

      return pageSlug === targetSlug || pageName === "login";
    });

    if (preview) {
      window.location.href = getTenantLoginTarget(project);
      return;
    }

    if (existingLoginPage) {
      selectPage(existingLoginPage.id);
      setActiveTab("design");
      setDesignPanel("Pages");
      return;
    }

    const loginPage = createPage("Login", [createLoginPageSection()]);
    loginPage.slug = targetSlug;
    loginPage.visibility = "public";

    updateProject((prev) => ({
      ...prev,
      siteChrome: {
        ...(prev.siteChrome || defaultSiteChrome),
        headerButtonLabel: "Login",
        authPageSlug: targetSlug,
      },
      pages: [...prev.pages, loginPage],
      activePageId: loginPage.id,
    }));

    setSelected({ type: "page", id: loginPage.id });
    setActiveTab("design");
    setDesignPanel("Pages");
    showToast("Login page created.");
  };

  const renderSiteHeader = () => {
    const site = project.siteChrome || defaultSiteChrome;
    if (!site.showHeader) return null;

    const logoSrc = site.logoUrl;

    return (
      <header
        className={`built-site-header header-align-${site.headerAlign || "center"} ${selected.type === "siteHeader" ? "is-selected" : ""}`}
        onClick={(event) => {
          event.stopPropagation();
          if (!preview) setSelected({ type: "siteHeader", id: "site-header" });
        }}
      >
        <div className="built-site-header-inner">
          <button
            type="button"
            className="built-site-brand"
            onClick={(event) => {
              event.stopPropagation();
              const homePage = project.pages.find((page) => page.slug === "/") || project.pages[0];
              if (homePage) selectPage(homePage.id);
            }}
          >
            {logoSrc ? <img src={logoSrc} alt={`${site.brand || "Website"} logo`} /> : <span className="logo-fallback">M</span>}
            <span>{site.brand || "Website"}</span>
          </button>

          <nav className="built-site-nav">
            {project.pages.map((page) => (
              <button
                type="button"
                key={page.id}
                className={activePage?.id === page.id ? "active" : ""}
                onClick={(event) => {
                  event.stopPropagation();
                  selectPage(page.id);
                }}
              >
                {page.name}
              </button>
            ))}
          </nav>

          <button
          type="button"
          className="built-site-cta"
          onClick={(event) => {
            event.stopPropagation();
            openOrCreateLoginPage();
          }}
        >
          {site.headerButtonLabel || "Login"}
        </button>
        </div>
      </header>
    );
  };

  const renderSiteFooter = () => {
    const site = project.siteChrome || defaultSiteChrome;
    if (!site.showFooter) return null;

    const pageLinks = splitLines(site.footerShopLinks || "");
    const helpLinks = splitLines(site.footerHelpLinks || "About Us\nPolicies\nContact");
    const socialLinks = splitLines(site.footerSocialLinks || "Facebook\nLinkedIn\nX\nInstagram");
    const footerLinks = [...pageLinks, ...helpLinks];
    const footerBrand = site.footerStoreName || site.brand || "Your Brand";
    const footerInitial = footerBrand.trim().slice(0, 1).toUpperCase() || "B";
    const navigateFooterLink = (label) => {
      const normalizedLabel = label.toLowerCase().trim();
      const target = project.pages.find((page) => {
        const normalizedName = page.name.toLowerCase().trim();
        const normalizedSlug = page.slug.toLowerCase().replace(/^\//, "");
        return normalizedName === normalizedLabel || normalizedSlug === normalizedLabel.replace(/\s+/g, "-");
      });

      if (target) selectPage(target.id);
    };

    return (
      <footer
        className={`built-site-footer ecommerce-style-footer ${selected.type === "siteFooter" ? "is-selected" : ""}`}
        onClick={(event) => {
          event.stopPropagation();
          if (!preview) setSelected({ type: "siteFooter", id: "site-footer" });
          if (event.target.closest(".powered-by-madar")) {
            window.location.href = site.madarLink || "/";
          }
        }}
      >
        <div className="ecommerce-footer-grid">
          <div className="ecommerce-footer-brand">
            <div className="ecommerce-footer-logo-row">
              {site.logoUrl ? (
                <img className="ecommerce-footer-logo" src={site.logoUrl} alt={`${footerBrand} logo`} />
              ) : (
                <div className="ecommerce-footer-logo footer-logo-fallback">{footerInitial}</div>
              )}
              <h3>{footerBrand}</h3>
            </div>

            <p>{site.description}</p>

            <div className="ecommerce-social-row">
              {socialLinks.map((item) => (
                <button type="button" key={item} aria-label={item}>
                  {item.slice(0, 2).toUpperCase()}
                </button>
              ))}
            </div>

          </div>

          <div className="ecommerce-footer-column ecommerce-footer-links-column">
            <h4>Links</h4>
            <div className="ecommerce-footer-links-grid">
              {footerLinks.map((item) => <button type="button" key={item} onClick={() => navigateFooterLink(item)}>{item}</button>)}
            </div>
          </div>

          <div className="ecommerce-footer-contact">
            <h4>Contact</h4>
            <div className="footer-language-pill">
              <span>◎</span>
              <strong>{site.footerLanguageLabel || "AR"}</strong>
            </div>
            <p>{site.contactEmail || "info@madar.com"}</p>
            <p dir="ltr">{site.phone || "+972599203857"}</p>
          </div>
        </div>

        <div className="ecommerce-footer-bottom">
          <p>© 2026 {site.footerStoreName || site.brand || "Your Website"}. {site.rights || "All rights reserved."}</p>
          <button type="button" className="powered-by-madar">Powered by Madar</button>
        </div>
      </footer>
    );
  };

  const renderDesignTab = () => (
    <div className="builder-layout">
      {!preview && (
        <aside className="builder-sidebar">
          <div className="panel-mode-select">
            <label>
              Editing panel
              <select value={designPanel} onChange={(event) => setDesignPanel(event.target.value)}>
                {designPanels.map((panel) => <option key={panel} value={panel}>{panel}</option>)}
              </select>
            </label>
          </div>

          {designPanel === "Pages" && (
            <section className="builder-panel">
              <h2>Pages</h2>
              <p className="panel-help">Create public pages, dashboards, forms, and review screens.</p>

              <select value={activePage?.id || ""} onChange={(event) => selectPage(event.target.value)}>
                {project.pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}
              </select>

              <div className="compact-actions">
                <button type="button" onClick={addPage}>+ Page</button>
                <button type="button" onClick={duplicatePage}>Duplicate</button>
                <button type="button" onClick={() => setModal("starter")}>Starter</button>
                <button type="button" className="danger-lite" onClick={deleteActivePage}>Delete</button>
              </div>
            </section>
          )}

          {designPanel === "Sections" && (
            <section className="builder-panel">
              <h2>Sections</h2>
              <p className="panel-help">Add page blocks. Auto layout is recommended.</p>
              <button type="button" className="full-width-action" onClick={() => setModal("section")}>+ Add Section</button>
              {selectedSection && (
                <div className="compact-actions">
                  <button type="button" onClick={duplicateSelectedSection}>Duplicate</button>
                  <button type="button" className="danger-lite" onClick={deleteSelectedSection}>Delete</button>
                </div>
              )}
            </section>
          )}

          {designPanel === "Layers" && (
            <section className="builder-panel">
              <h2>Layers</h2>
              <div className="layer-tree">
                {activePage?.sections.map((section) => (
                  <div key={section.id} className="layer-item">
                    <button
                      type="button"
                      className={selected.id === section.id ? "active" : ""}
                      onClick={() => setSelected({ type: "section", id: section.id })}
                    >
                      ▾ {section.name}
                    </button>

                    <div className="layer-children">
                      {section.mode === "free"
                        ? section.freeElements.map((element) => (
                            <button
                              type="button"
                              key={element.id}
                              className={selected.id === element.id ? "active" : ""}
                              onClick={() => setSelected({ type: "element", id: element.id })}
                            >
                              {element.name}
                            </button>
                          ))
                        : section.rows.map((row) =>
                            row.columns.map((column, index) => {
                              const columnCount = row.columns?.length || 1;

                              return (
                              <div key={column.id} className="layer-column">
                                <button
                                  type="button"
                                  className={selected.id === column.id ? "active" : ""}
                                  onClick={() => setSelected({ type: "column", id: column.id })}
                                >
                                  {getColumnDisplayName(index, columnCount)}
                                </button>

                                {column.elements.map((element) => (
                                  <button
                                    type="button"
                                    key={element.id}
                                    className={selected.id === element.id ? "active" : ""}
                                    onClick={() => setSelected({ type: "element", id: element.id })}
                                  >
                                    {element.name}
                                  </button>
                                ))}
                              </div>
                            );
                            })
                          )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {designPanel === "Elements" && (
            <section className="builder-panel">
              <h2>Add Elements</h2>
              <p className="panel-help">Select a section or column, then add an element.</p>

              {["Content", "Dashboard", "Auth", "Connected"].map((group) => (
                <div key={group} className="add-group">
                  <span>{group}</span>
                  {elementTypes
                    .filter((item) => item.group === group)
                    .map((item) => (
                      <button type="button" key={item.id} onClick={() => smartAddElement(item.id)}>
                        + {item.label}
                      </button>
                    ))}
                </div>
              ))}
            </section>
          )}
        </aside>
      )}

      <main
        className="builder-canvas-shell"
        onClick={() => {
          if (!preview) setSelected({ type: "page", id: activePage?.id });
        }}
      >
        <div
          className={`builder-canvas viewport-${viewport}`}
          style={{ maxWidth: preview ? `${viewports[viewport]}px` : undefined }}
        >
          {renderSiteHeader()}

          {activePage?.sections.map((section) => {
            const isSelected = selected.type === "section" && selected.id === section.id;

            if (section.mode === "free") {
              return (
                <section
                  key={section.id}
                  className={`site-section free-canvas-section width-${section.layout.width} ${isSelected ? "is-selected" : ""}`}
                  style={{ backgroundColor: section.layout.background, minHeight: section.layout.minHeight }}
                  onClick={(event) => {
                    event.stopPropagation();
                    if (!preview) setSelected({ type: "section", id: section.id });
                  }}
                >
                  {!preview && (
                    <div className="free-canvas-toolbar">
                      <strong>Free Canvas</strong>
                      <button type="button" onClick={() => setSelected({ type: "page", id: activePage.id })}>Exit</button>
                    </div>
                  )}

                  <div
                    className="free-canvas-frame"
                    style={{ width: `${viewports[viewport]}px`, minHeight: `${section.layout.minHeight}px` }}
                  >
                    {section.freeElements.map((element) => renderElement(element, true))}
                  </div>
                </section>
              );
            }

            return (
              <section
                key={section.id}
                className={`site-section width-${section.layout.width} padding-${section.layout.paddingY} ${isSelected ? "is-selected" : ""}`}
                style={{ backgroundColor: section.layout.background }}
                onClick={(event) => {
                  event.stopPropagation();
                  if (!preview) setSelected({ type: "section", id: section.id });
                }}
              >
                {section.rows.map((row) => (
                  <div
                    key={row.id}
                    className={`site-row columns-${row.layout.columns} align-${row.layout.align} gap-${row.layout.gap}`}
                  >
                    {row.columns.map((column) => {
                      const columnSelected = selected.type === "column" && selected.id === column.id;

                      return (
                        <div
                          key={column.id}
                          className={`site-column column-align-${column.layout.align} ${columnSelected ? "is-selected" : ""}`}
                          onClick={(event) => {
                            event.stopPropagation();
                            if (!preview) setSelected({ type: "column", id: column.id });
                          }}
                        >
                          {column.elements.map((element) => renderElement(element, false))}
                          {!preview && column.elements.length === 0 && (
                            <div className="empty-column">Select this column, then add an element.</div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ))}
              </section>
            );
          })}

          {renderSiteFooter()}
        </div>
      </main>

      {!preview && renderInspector()}
    </div>
  );

  const renderInspector = () => (
    <aside className="builder-inspector">
      <div className="inspector-title">
        <h2>Inspector</h2>
        <span>{selected.type}</span>
      </div>

      {selected.type === "page" && activePage && (
        <div className="inspector-group">
          <h3>Page Settings</h3>
          <label>Page name<input value={activePage.name} onChange={(event) => updateActivePage((page) => ({ ...page, name: event.target.value }))} /></label>
          <label>Page link<input value={activePage.slug} onChange={(event) => updateActivePage((page) => ({ ...page, slug: event.target.value }))} /></label>
          <label>Page background<input type="color" value={activePage.backgroundColor || "#ffffff"} onChange={(event) => updateActivePage((page) => ({ ...page, backgroundColor: event.target.value }))} /></label>

          <details>
            <summary>Website Header & Footer</summary>
            <label>Brand name<input value={project.siteChrome?.brand || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), brand: event.target.value } }))} /></label>
            <label>Contact email<input value={project.siteChrome?.contactEmail || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), contactEmail: event.target.value } }))} /></label>
            <label>Phone<input value={project.siteChrome?.phone || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), phone: event.target.value } }))} /></label>
            <label>Logo URL<input value={project.siteChrome?.logoUrl || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), logoUrl: event.target.value } }))} /></label>
            <label className="upload-image-button">Upload logo<input type="file" accept="image/*" onChange={(event) => uploadSiteLogo(event.target.files?.[0])} /></label>
            <label>Footer brand name<input value={project.siteChrome?.footerStoreName || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerStoreName: event.target.value } }))} /></label>
            <label>Footer description<textarea value={project.siteChrome?.description || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), description: event.target.value } }))} /></label>
            <label>Footer rights<input value={project.siteChrome?.rights || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), rights: event.target.value } }))} /></label>
            <label>Footer pages<textarea value={project.siteChrome?.footerShopLinks || ""} placeholder="One link per line" onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerShopLinks: event.target.value } }))} /></label>
            <label>Footer help links<textarea value={project.siteChrome?.footerHelpLinks || ""} placeholder="One link per line" onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerHelpLinks: event.target.value } }))} /></label>
            <label>Social links<textarea value={project.siteChrome?.footerSocialLinks || ""} placeholder="One item per line" onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerSocialLinks: event.target.value } }))} /></label>
          </details>
        </div>
      )}

      {selected.type === "siteHeader" && (
        <div className="inspector-group">
          <h3>Header</h3>
          <label>Brand name<input value={project.siteChrome?.brand || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), brand: event.target.value } }))} /></label>
          <label>Logo URL<input value={project.siteChrome?.logoUrl || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), logoUrl: event.target.value } }))} /></label>
          <label className="upload-image-button">Upload logo<input type="file" accept="image/*" onChange={(event) => uploadSiteLogo(event.target.files?.[0])} /></label>
          <label>Header login button<input value={project.siteChrome?.headerButtonLabel || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), headerButtonLabel: event.target.value } }))} /></label>
<label>Login page slug<input value={project.siteChrome?.authPageSlug || "/login"} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), authPageSlug: event.target.value || "/login" } }))} /></label>
          <label>Header alignment<select value={project.siteChrome?.headerAlign || "center"} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), headerAlign: event.target.value } }))}>
            <option value="left">Left</option>
            <option value="center">Center</option>
            <option value="right">Right</option>
          </select></label>
        </div>
      )}

      {selected.type === "siteFooter" && (
        <div className="inspector-group">
          <h3>Footer</h3>
          <label>Footer brand name<input value={project.siteChrome?.footerStoreName || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerStoreName: event.target.value } }))} /></label>
          <label>Footer description<textarea value={project.siteChrome?.description || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), description: event.target.value } }))} /></label>
          <label>Contact email<input value={project.siteChrome?.contactEmail || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), contactEmail: event.target.value } }))} /></label>
          <label>Phone<input value={project.siteChrome?.phone || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), phone: event.target.value } }))} /></label>
          <label>Footer pages<textarea value={project.siteChrome?.footerShopLinks || ""} placeholder="One link per line" onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerShopLinks: event.target.value } }))} /></label>
          <label>Footer help links<textarea value={project.siteChrome?.footerHelpLinks || ""} placeholder="One link per line" onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerHelpLinks: event.target.value } }))} /></label>
          <label>Social links<textarea value={project.siteChrome?.footerSocialLinks || ""} placeholder="One item per line" onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), footerSocialLinks: event.target.value } }))} /></label>
          <label>Footer rights<input value={project.siteChrome?.rights || ""} onChange={(event) => updateProject((prev) => ({ ...prev, siteChrome: { ...(prev.siteChrome || defaultSiteChrome), rights: event.target.value } }))} /></label>
        </div>
      )}

      {selected.type === "section" && selectedSection && (
        <div className="inspector-group">
          <h3>Section</h3>
          <label>Name<input value={selectedSection.name} onChange={(event) => updateSelectedSection({ name: event.target.value })} /></label>
          <label>Background<input type="color" value={selectedSection.layout.background === "transparent" ? "#ffffff" : selectedSection.layout.background} onChange={(event) => updateSelectedSection({ layout: { background: event.target.value } })} /></label>
          <label>Width<select value={selectedSection.layout.width} onChange={(event) => updateSelectedSection({ layout: { width: event.target.value } })}>{sectionWidths.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          <label>Padding<select value={selectedSection.layout.paddingY} onChange={(event) => updateSelectedSection({ layout: { paddingY: event.target.value } })}>{spacingOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          {selectedSection.mode === "free" && <label>Minimum height<input type="number" value={selectedSection.layout.minHeight} onChange={(event) => updateSelectedSection({ layout: { minHeight: Number(event.target.value) } })} /></label>}
          {selectedSection.mode === "auto" && (
            <details open>
              <summary>Rows and columns</summary>
              <button type="button" className="full-width-action" onClick={addRowToSelectedSection}>+ Add Row</button>
              <div className="row-editor-list">
                {(selectedSection.rows || []).map((row, index) => (
                  <div className="row-editor-card" key={row.id}>
                    <div className="row-editor-header">
                      <strong>Row {index + 1}</strong>
                      <div>
                        <button type="button" onClick={() => duplicateSectionRow(row.id)}>Duplicate</button>
                        <button type="button" className="danger-lite" onClick={() => deleteSectionRow(row.id)}>Delete</button>
                      </div>
                    </div>
                    <label>Columns<select value={row.layout.columns} onChange={(event) => setRowColumnCount(row.id, Number(event.target.value))}>{columnOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
                    <label>Alignment<select value={row.layout.align} onChange={(event) => updateSectionRow(row.id, { layout: { align: event.target.value } })}>{["start", "center", "stretch"].map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
                    <label>Gap<select value={row.layout.gap} onChange={(event) => updateSectionRow(row.id, { layout: { gap: event.target.value } })}>{spacingOptions.filter((item) => item.value !== "none").map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      {selected.type === "column" && selectedColumn && (
        <div className="inspector-group">
          <h3>Column</h3>
          <label>Alignment<select value={selectedColumn.layout.align} onChange={(event) => updateSelectedColumn({ layout: { align: event.target.value } })}>{alignmentOptions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
        </div>
      )}

      {selected.type === "element" && selectedElement && (
        <div className="inspector-group">
          <h3>Element</h3>
          <label>Name<input value={selectedElement.name} onChange={(event) => updateSelectedElement({ name: event.target.value })} /></label>
          {["loginBlock", "registrationBlock"].includes(selectedElement.type) ? (
            <details open>
              <summary>Auth content</summary>
              <label>Title<input value={getAuthBlockConfig(selectedElement).title} onChange={(event) => updateSelectedAuthBlock({ title: event.target.value })} /></label>
              <label>Subtitle<textarea value={getAuthBlockConfig(selectedElement).subtitle} onChange={(event) => updateSelectedAuthBlock({ subtitle: event.target.value })} /></label>
              <label>Button text<input value={getAuthBlockConfig(selectedElement).buttonText} onChange={(event) => updateSelectedAuthBlock({ buttonText: event.target.value })} /></label>
              <label>Switch text<input value={getAuthBlockConfig(selectedElement).switchText} onChange={(event) => updateSelectedAuthBlock({ switchText: event.target.value })} /></label>
              <label>Switch action<input value={getAuthBlockConfig(selectedElement).switchActionText} onChange={(event) => updateSelectedAuthBlock({ switchActionText: event.target.value })} /></label>
            </details>
          ) : selectedElement.type === "reservationBlock" ? (
            <details open>
              <summary>Reservation content</summary>
              <label>Title<input value={getReservationBlockConfig(selectedElement).title} onChange={(event) => updateSelectedReservationBlock({ title: event.target.value })} /></label>
              <label>Description<textarea value={getReservationBlockConfig(selectedElement).description} onChange={(event) => updateSelectedReservationBlock({ description: event.target.value })} /></label>
              <label>Services<textarea value={getReservationBlockConfig(selectedElement).services.join("\n")} onChange={(event) => updateSelectedReservationBlock({ services: splitLines(event.target.value) })} /></label>
              <label>Button text<input value={getReservationBlockConfig(selectedElement).submitLabel} onChange={(event) => updateSelectedReservationBlock({ submitLabel: event.target.value })} /></label>
              <div className="reservation-field-picker">
                <strong>Needed data</strong>
                {reservationFieldOptions.map((field) => {
                  const config = getReservationBlockConfig(selectedElement);
                  const checked = config.fields.includes(field.id);

                  return (
                    <label className="checkbox-control" key={field.id}>
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(event) => {
                          const nextFields = event.target.checked
                            ? [...config.fields, field.id]
                            : config.fields.filter((item) => item !== field.id);

                          updateSelectedReservationBlock({
                            fields: nextFields.length > 0 ? nextFields : [field.id],
                          });
                        }}
                      />
                      {field.label}
                    </label>
                  );
                })}
              </div>
              <button type="button" className="full-width-action" onClick={moveSelectedReservationToWideSection}>Move to wide section</button>
            </details>
          ) : (
            <label>Content<textarea value={selectedElement.content} onChange={(event) => updateSelectedElement({ content: event.target.value })} /></label>
          )}
          <label>Text color<input type="color" value={selectedElement.styles.color || "#1a2744"} onChange={(event) => updateSelectedElement({ styles: { color: event.target.value } })} /></label>
          <label>Background<input type="color" value={selectedElement.styles.backgroundColor || "#ffffff"} onChange={(event) => updateSelectedElement({ styles: { backgroundColor: event.target.value } })} /></label>
          <label>Font size<input value={selectedElement.styles.fontSize || ""} placeholder="Example: 18px" onChange={(event) => updateSelectedElement({ styles: { fontSize: event.target.value } })} /></label>
          <label>Border radius<input value={selectedElement.styles.borderRadius || ""} placeholder="Example: 16px" onChange={(event) => updateSelectedElement({ styles: { borderRadius: event.target.value } })} /></label>
          {selectedElement.mode !== "free" && (
            <details open>
              <summary>Size and placement</summary>
              <label>Width ratio<select value={selectedElement.styles.width || "auto"} onChange={(event) => updateSelectedElement({ styles: { width: event.target.value === "auto" ? "" : event.target.value } })}>
                <option value="auto">Natural size</option>
                <option value="100%">Full width</option>
                <option value="75%">Wide - 3/4</option>
                <option value="50%">Half - 1/2</option>
                <option value="33.333%">Small - 1/3</option>
              </select></label>
              <label>Placement<select value={selectedElement.styles.alignSelf || "auto"} onChange={(event) => updateSelectedElement({ styles: { alignSelf: event.target.value } })}>
                <option value="auto">Use column setting</option>
                <option value="flex-start">Left</option>
                <option value="center">Center</option>
                <option value="flex-end">Right</option>
                <option value="stretch">Stretch</option>
              </select></label>
            </details>
          )}

          {(selectedElement.type === "formBlock" || selectedElement.type === "responsesTable") && (
            <label>Connected form<select value={selectedElement.connectedFormId || ""} onChange={(event) => updateSelectedElement({ connectedFormId: event.target.value })}>{project.forms.map((form) => <option key={form.id} value={form.id}>{form.title}</option>)}</select></label>
          )}

          {selectedElement.type === "image" && (
            <label className="upload-image-button">Upload image<input type="file" accept="image/*" onChange={(event) => uploadImageForSelectedElement(event.target.files?.[0])} /></label>
          )}

          {selectedElement.mode === "free" && (
            <details open>
              <summary>Size and position: {viewport}</summary>
              {[
                ["x", "Left"],
                ["y", "Top"],
                ["width", "Width"],
                ["height", "Height"],
              ].map(([key, label]) => (
                <label key={key}>
                  {label} (% of full canvas)
                  <input
                    type="number"
                    min="-100"
                    max="200"
                    value={getElementPositionPercent(key)}
                    onChange={(event) => updateElementPositionPercent(key, event.target.value)}
                  />
                </label>
              ))}
            </details>
          )}

          {selectedElement.type === "button" && (
            <details>
              <summary>Interaction</summary>
              <label>Action<select value={selectedElement.action?.type || "none"} onChange={(event) => updateSelectedElement({ action: { type: event.target.value } })}>
                <option value="none">None</option>
                <option value="goToPage">Go to page</option>
                <option value="openUrl">Open URL</option>
                <option value="showMessage">Show message</option>
              </select></label>
              {selectedElement.action?.type === "goToPage" && (
                <label>Target page<select value={selectedElement.action?.pageId || ""} onChange={(event) => updateSelectedElement({ action: { pageId: event.target.value } })}>{project.pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}</select></label>
              )}
              {selectedElement.action?.type === "openUrl" && (
                <label>URL<input value={selectedElement.action?.url || ""} onChange={(event) => updateSelectedElement({ action: { url: event.target.value } })} /></label>
              )}
              {selectedElement.action?.type === "showMessage" && (
                <label>Message<input value={selectedElement.action?.message || ""} onChange={(event) => updateSelectedElement({ action: { message: event.target.value } })} /></label>
              )}
            </details>
          )}

          <details open>
            <summary>Element actions</summary>
            <div className="element-action-grid">
              <button type="button" onClick={duplicateSelectedElement}>Duplicate</button>
              <button type="button" onClick={() => moveSelectedElement("up")}>Move up</button>
              <button type="button" onClick={() => moveSelectedElement("down")}>Move down</button>
            </div>
            {findElementLocation(selectedElement.id)?.isFree === false && (
              <label>Move this element to<select value={findElementLocation(selectedElement.id)?.columnId || ""} onChange={(event) => moveSelectedElementToColumn(event.target.value)}>
                {activePage?.sections.flatMap((section, sectionIndex) =>
                  (section.rows || []).flatMap((row) =>
                    row.columns.map((column, columnIndex) => (
                      <option key={column.id} value={column.id}>
                        {getColumnOptionLabel(section, row, columnIndex, sectionIndex)}
                      </option>
                    ))
                  )
                )}
              </select></label>
            )}
          </details>

          <button type="button" className="danger-button" onClick={deleteSelectedElement}>Delete Element</button>
        </div>
      )}
    </aside>
  );

  const renderDataTab = () => (
    <div className="workspace-page">
      <div className="workspace-header">
        <div>
          <h2>Data Logs</h2>
          <p>Manage the records and collections created from forms, logs, requests, orders, reports, and other system data.</p>
        </div>
        <button type="button" onClick={addCollection}>+ Collection</button>
      </div>

      <div className="forms-layout">
        <aside className="object-list">
          {project.collections.map((collection) => (
            <button key={collection.id} type="button" className={activeCollection?.id === collection.id ? "active" : ""} onClick={() => selectCollection(collection.id)}>
              <strong>{collection.name}</strong>
              <span>{collection.fields.length} fields · {(collection.records || []).length} records</span>
            </button>
          ))}
        </aside>

        <section className="form-editor">
          {activeCollection && (
            <>
              <div className="editor-card-header">
                <h3>{activeCollection.name}</h3>
                <button type="button" onClick={addFieldToCollection}>+ Field</button>
              </div>

              <label>Collection name<input value={activeCollection.name} onChange={(event) => updateActiveCollection((collection) => ({ ...collection, name: event.target.value }))} /></label>
              <label>Description<textarea value={activeCollection.description} onChange={(event) => updateActiveCollection((collection) => ({ ...collection, description: event.target.value }))} /></label>

              <div className="field-list">
                {activeCollection.fields.map((field) => (
                  <div className="field-row" key={field.id}>
                    <input value={field.label} onChange={(event) => updateCollectionField(field.id, { label: event.target.value })} />
                    <select value={field.type} onChange={(event) => updateCollectionField(field.id, { type: event.target.value })}>
                      {fieldTypes.map((type) => <option key={type.id} value={type.id}>{type.label}</option>)}
                    </select>
                    <label className="checkbox-control compact-check"><input type="checkbox" checked={field.required} onChange={(event) => updateCollectionField(field.id, { required: event.target.checked })} /> Required</label>
                    <button type="button" className="danger-lite" onClick={() => deleteCollectionField(field.id)}>Delete</button>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );

  const renderFormsTab = () => {
    const commonFieldTypes = ["shortText", "paragraph", "email", "phone", "dropdown", "radio", "checkboxes", "date"];
    const placements = activeForm ? getFormPlacements(activeForm.id) : [];

    return (
    <div className="workspace-page forms-google-workspace">
      <div className="workspace-header">
        <div>
          <h2>Forms</h2>
          <p>Create the form first. Then place it on any design page with one click.</p>
        </div>
        <button type="button" onClick={addForm}>+ Form</button>
      </div>

      <div className="google-form-layout">
        <aside className="object-list google-form-list">
          {project.forms.map((form) => (
            <button key={form.id} type="button" className={activeForm?.id === form.id ? "active" : ""} onClick={() => selectForm(form.id)}>
              <strong>{form.title}</strong>
              <span>{getFormFields(form).length} fields · {form.responses.length} responses</span>
            </button>
          ))}
        </aside>

        <main className="google-form-document">
          {activeForm && (
            <>
              <div className="google-form-title-card">
                <input className="google-form-title-input" value={activeForm.title} onChange={(event) => updateActiveForm((form) => ({ ...form, title: event.target.value }))} />
                <textarea className="google-form-description-input" value={activeForm.description} placeholder="Form description" onChange={(event) => updateActiveForm((form) => ({ ...form, description: event.target.value }))} />
              </div>

              <div className="google-add-strip">
                {commonFieldTypes.map((typeId) => {
                  const type = getFieldType(typeId);
                  return (
                    <button key={type.id} type="button" onClick={() => addFieldToForm(type.id)}>
                      + {type.label}
                    </button>
                  );
                })}
                <button type="button" className="add-section-control" onClick={addFormSection}>+ Section</button>
              </div>

              <div className="form-sections-stack">
                {getFormSections(activeForm).map((section, sectionIndex) => (
                  <section className="form-section-card google-section-card" key={section.id}>
                    <div className="google-section-header">
                      <input className="section-title-input" value={section.title} onChange={(event) => updateFormSection(section.id, { title: event.target.value })} />
                      <button type="button" className="danger-lite" disabled={getFormSections(activeForm).length <= 1} onClick={() => deleteFormSection(section.id)}>Delete section</button>
                    </div>
                    <textarea className="section-description-input" value={section.description || ""} placeholder="Section description" onChange={(event) => updateFormSection(section.id, { description: event.target.value })} />
                    {(section.fields || []).map((field) => (
                      <article className={`question-card google-question-card ${selected.id === field.id ? "active" : ""}`} key={field.id} onClick={() => setSelected({ type: "field", id: field.id })}>
                        <div className="question-main">
                          <div className="google-question-topline">
                            <input className="question-title-input" value={field.label} placeholder="Question" onChange={(event) => updateFormField(field.id, { label: event.target.value })} />
                            <select value={field.type} onChange={(event) => updateFormField(field.id, { type: event.target.value })}>
                              {fieldTypes.map((type) => <option key={type.id} value={type.id}>{type.label}</option>)}
                            </select>
                          </div>
                          <input value={field.placeholder || ""} placeholder="Help text or placeholder" onChange={(event) => updateFormField(field.id, { placeholder: event.target.value })} />
                          {["dropdown", "radio", "checkboxes", "status"].includes(field.type) && (
                            <textarea className="options-editor" value={(field.options || []).join("\n")} placeholder="One option per line" onChange={(event) => updateFormField(field.id, { options: splitLines(event.target.value) })} />
                          )}
                        </div>
                        <div className="question-footer-actions">
                          <span>Question {sectionIndex + 1}.{(section.fields || []).findIndex((item) => item.id === field.id) + 1}</span>
                          <button type="button" onClick={(event) => { event.stopPropagation(); moveFormField(field.id, "up"); }}>Up</button>
                          <button type="button" onClick={(event) => { event.stopPropagation(); moveFormField(field.id, "down"); }}>Down</button>
                          <button type="button" onClick={(event) => { event.stopPropagation(); duplicateFormField(field.id); }}>Duplicate</button>
                          <label className="checkbox-control"><input type="checkbox" checked={field.required} onChange={(event) => updateFormField(field.id, { required: event.target.checked })} /> Required</label>
                          <button type="button" className="danger-lite" onClick={(event) => { event.stopPropagation(); deleteFormField(field.id); }}>Delete</button>
                        </div>
                      </article>
                    ))}
                    <button type="button" className="add-question-wide" onClick={() => addFieldToForm("shortText", section.id)}>+ Add question</button>
                  </section>
                ))}
              </div>
            </>
          )}
        </main>

        <aside className="form-side-settings google-form-actions">
          <section>
            <h3>Place Form</h3>
            <label>
              Page
              <select value={project.activePageId || ""} onChange={(event) => selectPage(event.target.value)}>
                {project.pages.map((page) => <option key={page.id} value={page.id}>{page.name}</option>)}
              </select>
            </label>
            <button type="button" className="primary-action" onClick={() => addConnectedFormSectionToPage(activeForm?.id)}>
              Add to page
            </button>
            <button type="button" onClick={() => addConnectedResponsesSectionToPage(activeForm?.id)}>
              Add responses
            </button>
            {placements.length > 0 && (
              <div className="connected-placement-list">
                <span>Placed on:</span>
                {placements.map((placement) => (
                  <button
                    type="button"
                    key={`${placement.pageId}_${placement.sectionName}`}
                    onClick={() => {
                      selectPage(placement.pageId);
                      setActiveTab("design");
                      setDesignPanel("Layers");
                    }}
                  >
                    {placement.pageName}
                  </button>
                ))}
              </div>
            )}
          </section>

          <section>
            <h3>Save Data</h3>
            <label>
              Save submissions to
              <select value={activeForm?.connectedCollectionId || ""} onChange={(event) => updateActiveForm((form) => ({ ...form, connectedCollectionId: event.target.value }))}>
                <option value="">Form submissions only</option>
                {project.collections.map((collection) => <option key={collection.id} value={collection.id}>{collection.name}</option>)}
              </select>
            </label>
            <label>
              Success message
              <textarea value={activeForm?.successMessage || ""} onChange={(event) => updateActiveForm((form) => ({ ...form, successMessage: event.target.value }))} />
            </label>
          </section>

          <section>
            <h3>Preview</h3>
            {activeForm && renderConnectedForm(activeForm.id)}
          </section>

        </aside>
      </div>
    </div>
  );
  };

  const renderWorkflowsTab = () => (
    <div className="workspace-page">
      <div className="workspace-header">
        <div>
          <h2>Workflows</h2>
          <p>Front-end workflow prototypes. These describe what backend automation should do later.</p>
        </div>
        <button type="button" onClick={addWorkflow}>+ Workflow</button>
      </div>

      <div className="forms-layout">
        <aside className="object-list">
          {project.workflows.map((workflow) => (
            <button key={workflow.id} type="button" className={activeWorkflow?.id === workflow.id ? "active" : ""} onClick={() => selectWorkflow(workflow.id)}>
              <strong>{workflow.name}</strong>
              <span>{workflow.enabled ? "Enabled" : "Disabled"} · {workflow.steps.length} steps</span>
            </button>
          ))}
        </aside>

        <section className="form-editor">
          {activeWorkflow && (
            <>
              <div className="editor-card-header">
                <h3>{activeWorkflow.name}</h3>
                <button type="button" onClick={addWorkflowStep}>+ Step</button>
              </div>

              <label>Workflow name<input value={activeWorkflow.name} onChange={(event) => updateActiveWorkflow((workflow) => ({ ...workflow, name: event.target.value }))} /></label>
              <label>Connected form<select value={activeWorkflow.formId || ""} onChange={(event) => updateActiveWorkflow((workflow) => ({ ...workflow, formId: event.target.value }))}>{project.forms.map((form) => <option key={form.id} value={form.id}>{form.title}</option>)}</select></label>
              <label className="checkbox-control"><input type="checkbox" checked={activeWorkflow.enabled} onChange={(event) => updateActiveWorkflow((workflow) => ({ ...workflow, enabled: event.target.checked }))} /> Enabled</label>

              <div className="automations-grid">
                {activeWorkflow.steps.map((step, index) => (
                  <div className="automation-card" key={step.id}>
                    <div className="automation-card-header">
                      <strong>Step {index + 1}</strong>
                      <button type="button" className="danger-lite" onClick={() => deleteWorkflowStep(step.id)}>Delete</button>
                    </div>
                    <label>Type<select value={step.type} onChange={(event) => updateWorkflowStep(step.id, { type: event.target.value })}>{workflowStepTypes.map((type) => <option key={type.id} value={type.id}>{type.label}</option>)}</select></label>
                    <label>Label<input value={step.label} onChange={(event) => updateWorkflowStep(step.id, { label: event.target.value })} /></label>
                    <label>Details<textarea value={step.details} onChange={(event) => updateWorkflowStep(step.id, { details: event.target.value })} /></label>
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );

  const renderThemeTab = () => (
    <div className="workspace-page">
      <div className="workspace-header">
        <div>
          <h2>Theme</h2>
          <p>Global design system values applied to the builder and preview shell.</p>
        </div>
      </div>

      <section className="theme-grid">
        {[
          ["background", "App background"],
          ["surface", "Surface"],
          ["softSurface", "Soft surface"],
          ["text", "Text"],
          ["muted", "Muted"],
          ["primary", "Primary"],
          ["accent", "Accent"],
          ["accentDark", "Accent dark"],
        ].map(([key, label]) => (
          <label className="theme-control" key={key}>
            {label}
            <input type="color" value={project.theme[key]} onChange={(event) => updateProject((prev) => ({ ...prev, theme: { ...prev.theme, [key]: event.target.value } }))} />
          </label>
        ))}
        <label className="theme-control">Radius<input type="number" value={project.theme.radius} onChange={(event) => updateProject((prev) => ({ ...prev, theme: { ...prev.theme, radius: Number(event.target.value) } }))} /></label>
        <label className="theme-control">Font family<input value={project.theme.fontFamily} onChange={(event) => updateProject((prev) => ({ ...prev, theme: { ...prev.theme, fontFamily: event.target.value } }))} /></label>
      </section>
    </div>
  );

  const renderResponsesTab = () => (
    <div className="workspace-page">
      <div className="workspace-header">
        <div>
          <h2>Submissions</h2>
          <p>Review form submissions and collected data from the system.</p>
        </div>
      </div>

      <div className="responses-grid">
        {project.forms.map((form) => (
          <section className="responses-page-card" key={form.id}>
            <div className="responses-page-header">
              <div>
                <h3>{form.title}</h3>
                <p>{form.responses.length} responses</p>
              </div>
            </div>
            {renderResponsesTable(form.id)}
          </section>
        ))}
      </div>
    </div>
  );

  const renderPublishTab = () => {
    const subdomain = project.publish?.subdomain || "";
    const siteBaseDomain = project.publish?.siteBaseDomain || "madar.app";
    const customDomain = project.publish?.customDomain || "";
    const localSiteUrl = `/site/${subdomain || "my-site"}`;
    const productionUrl = customDomain
      ? `https://${customDomain}`
      : `https://${subdomain || "my-site"}.${siteBaseDomain}`;

    return (
      <div className="workspace-page">
        <div className="workspace-header">
          <div>
            <h2>Publish</h2>
            <p>Configure the public website URL, subdomain, local preview, and mock publishing.</p>
          </div>
        </div>

        <div className="publish-grid">
          <section className="publish-card">
            <h3>Status</h3>
            <p>Project: <strong>{project.name}</strong></p>
            <p>State: <strong>{project.status}</strong></p>
            <p>Local URL: <strong>{localSiteUrl}</strong></p>
            <p>Production URL: <strong>{productionUrl}</strong></p>
            <p>Last saved: <strong>{project.publish?.lastSavedAt || "Not saved yet"}</strong></p>
            <p>Last published: <strong>{project.publish?.lastPublishedAt || "Not published yet"}</strong></p>
          </section>

          <section className="publish-card">
            <h3>Website Address</h3>

            <label>
              Subdomain
              <input
                value={subdomain}
                placeholder="my-business"
                onChange={(event) =>
                  updatePublishSettings({
                    subdomain: sanitizeSubdomain(event.target.value),
                  })
                }
              />
            </label>

            <label>
              Base domain
              <input
                value={siteBaseDomain}
                placeholder="madar.app"
                onChange={(event) =>
                  updatePublishSettings({
                    siteBaseDomain: event.target.value.trim(),
                  })
                }
              />
            </label>

            <label>
              Custom domain later
              <input
                value={customDomain}
                placeholder="www.customer.com"
                onChange={(event) =>
                  updatePublishSettings({
                    customDomain: event.target.value.trim().toLowerCase(),
                  })
                }
              />
            </label>

            <div className="publish-actions">
              <button
                type="button"
                onClick={() => {
                  window.location.href = localSiteUrl;
                }}
              >
                Open local site
              </button>

              <button
                type="button"
                onClick={() => {
                  window.location.href = `${localSiteUrl}/login`;
                }}
              >
                Open login
              </button>
            </div>
          </section>

          <section className="publish-card">
            <h3>Actions</h3>
            <div className="publish-actions">
              <button type="button" onClick={saveProject}>Save locally</button>
              <button type="button" onClick={loadProject}>Load local save</button>
              <button type="button" onClick={exportProject}>Copy JSON export</button>
              <button type="button" className="primary-action" onClick={publishProject}>Publish mock</button>
            </div>
          </section>
        </div>
      </div>
    );
  };

  const renderActiveTab = () => {
    if (activeTab === "design") return renderDesignTab();
    if (activeTab === "data") return renderDataTab();
    if (activeTab === "forms") return renderFormsTab();
    if (activeTab === "responses") return renderResponsesTab();

    if (activeTab === "users") {
      return (
        <PageBuilderUsers
          project={project}
          updateProject={updateProject}
          selectedRole={selectedRole}
          setSelected={setSelected}
          showToast={showToast}
        />
      );
    }

    if (activeTab === "theme") return renderThemeTab();
    if (activeTab === "publish") return renderPublishTab();
    return renderDesignTab();
  };

  const renderWorkspaceNavigator = () => (
    <nav className="workspace-tabs" aria-label="Builder workspaces">
      {builderTabs
        .filter((tab) => !visibleTabIds || visibleTabIds.includes(tab.id))
        .map((tab) => (
        <button
          type="button"
          key={tab.id}
          className={activeTab === tab.id ? "active" : ""}
          onClick={() => setActiveTab(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  );

  const activeHelper =
    builderTabs.find((tab) => tab.id === activeTab)?.helper ||
    (activeTab === "responses"
      ? "Review submitted form answers."
      : activeTab === "data"
        ? "Prototype collections and fields in front-end state."
        : "");

  return (
    <div
      className={`page-builder ${preview ? "preview-mode" : ""}`}
      style={{
        "--madar-bg": project.theme.background,
        "--madar-surface": project.theme.surface,
        "--madar-surface-soft": project.theme.softSurface,
        "--madar-text": project.theme.text,
        "--madar-muted": project.theme.muted,
        "--madar-navy": project.theme.primary,
        "--madar-red": project.theme.accent,
        "--madar-red-dark": project.theme.accentDark,
        "--madar-radius": `${project.theme.radius}px`,
        fontFamily: project.theme.fontFamily,
      }}
      onMouseMove={handleMouseMove}
      onMouseUp={() => setDragState(null)}
      onMouseLeave={() => setDragState(null)}
    >
      <div className="builder-desktop-shell">
        <header className="builder-topbar">
          <div className="builder-brand">
            <h1>{project.name}</h1>
            <p>{activeHelper}</p>
          </div>

          <div className="builder-topbar-actions">
            <button type="button" onClick={() => setPreview((value) => !value)}>{preview ? "Exit Preview" : "Preview"}</button>
            <button type="button" onClick={saveProject}>Save</button>
            <button type="button" className="primary-action" onClick={publishProject}>Publish</button>
          </div>
        </header>

        {!preview && !hideWorkspaceTabs && (
          <div className="builder-subbar">
            {renderWorkspaceNavigator()}
          </div>
        )}

        {preview && (
          <div className="preview-device-toolbar">
            <div className="viewport-switcher">
              {Object.keys(viewports).map((item) => (
                <button
                  type="button"
                  key={item}
                  className={viewport === item ? "active" : ""}
                  onClick={() => setViewport(item)}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
        )}

        {renderActiveTab()}
      </div>

      <div className="builder-mobile-blocker">
        <div>
          <h2>Desktop builder only</h2>
          <p>The builder workspace is designed for tablet/desktop editing. The pages you build still include mobile preview behavior.</p>
        </div>
      </div>

      {modal === "section" && (
        <div className="builder-modal-backdrop" onClick={() => setModal(null)}>
          <div className="builder-modal" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h2>Add Section</h2>
              <button type="button" onClick={() => setModal(null)}>×</button>
            </div>
            <div className="section-library-grid">
              {sectionLibrary.map((section) => (
                <button type="button" className="section-card" key={section.id} onClick={() => addSection(section.create)}>
                  <span>{section.category}</span>
                  <strong>{section.title}</strong>
                  <p>{section.description}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {modal === "starter" && (
        <div className="builder-modal-backdrop" onClick={() => setModal(null)}>
          <div className="builder-modal wide" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h2>Choose Starter</h2>
              <button type="button" onClick={() => setModal(null)}>×</button>
            </div>
            <div className="starter-grid">
              {starterSystems.map((starter) => (
                <button type="button" className="starter-card" key={starter.id} onClick={() => applyStarter(starter.id)}>
                  <strong>{starter.title}</strong>
                  <p>{starter.subtitle}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {toast && <div className="builder-toast">{toast}</div>}
    </div>
  );
}
