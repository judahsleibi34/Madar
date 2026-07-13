import { createId, slugify, defaultPermissions, defaultTheme, defaultSiteChrome, fieldTypes } from "./PageBuilder.constants";
import { getFactoryContent } from "../../../content/pageBuilder";

const factoryCopy = getFactoryContent("en");

export const createPosition = () => ({
  desktop: { x: 56, y: 56, width: 380, height: 96 },
  tablet: { x: 40, y: 44, width: 320, height: 96 },
  mobile: { x: 22, y: 34, width: 300, height: 96 },
});

export const createAction = (type = "none", overrides = {}) => ({
  type,
  pageId: "",
  sectionId: "",
  formId: "",
  url: "",
  message: "",
  status: "",
  ...overrides,
});

export const createField = (label = factoryCopy.fields.untitled, type = "shortText", overrides = {}) => {
  const meta = fieldTypes.find((field) => field.id === type);
  const choiceDefaults = ["dropdown", "radio", "checkboxes", "status"].includes(type)
    ? factoryCopy.fields.options
    : [];

  return {
    id: createId("field"),
    label,
    type,
    key: slugify(label).replaceAll("-", "_"),
    required: false,
    helpText: "",
    placeholder: meta?.label || "",
    showDescriptionEditor: false,
    showExampleEditor: false,
    showDetailsEditor: false,
    options: choiceDefaults,
    defaultValue: "",
    scaleMin: 1,
    scaleMax: 5,
    scaleMinLabel: factoryCopy.fields.scaleMin,
    scaleMaxLabel: factoryCopy.fields.scaleMax,
    maxRating: 5,
    width: "full",
    quizCorrectAnswer: type === "checkboxes" ? [] : "",
    quizPoints: 1,
    ...overrides,
  };
};

export const createCollection = (name = factoryCopy.collection.name, fields = []) => ({
  id: createId("collection"),
  name,
  key: slugify(name).replaceAll("-", "_"),
  description: factoryCopy.collection.description,
  fields:
    fields.length > 0
      ? fields
      : [
          createField(factoryCopy.collection.defaultFields.title, "shortText", { required: true }),
          createField(factoryCopy.collection.defaultFields.status, "dropdown", {
            options: factoryCopy.collection.defaultFields.statusOptions,
            defaultValue: factoryCopy.collection.defaultFields.statusOptions[0],
          }),
          createField(factoryCopy.collection.defaultFields.createdBy, "shortText"),
        ],
  records: [],
});

export const createFormSection = (title = factoryCopy.form.sectionTitle, fields = []) => ({
  id: createId("formSection"),
  title,
  description: "",
  collapsed: false,
  fields,
});

export const createForm = (title = factoryCopy.form.title, fields = [], overrides = {}) => {
  const defaultFields =
    fields.length > 0
      ? fields
      : [
          createField(factoryCopy.form.defaultFields.fullName, "shortText", { required: true }),
          createField(factoryCopy.form.defaultFields.email, "email", { required: true }),
          createField(factoryCopy.form.defaultFields.details, "paragraph"),
        ];

  return {
    id: createId("form"),
    name: title,
    title,
    description: factoryCopy.form.description,
    successMessage: factoryCopy.form.successMessage,
    languageMode: "en",
    defaultLanguage: "en",
    connectedCollectionId: "",
    mode: "form",
    quiz: {
      lockScreen: false,
      totalTimeLimitSec: 0,
      questionTimeLimitSec: 0,
      showQuestionTimer: true,
      showTotalTimer: true,
      scoring: "automatic",
      passingScore: 70,
      showResults: true,
      allowRetakes: true,
      maxRetakes: 0,
    },
    pageMode: "paged",
    sections: [createFormSection(factoryCopy.form.sectionTitle, defaultFields)],
    responses: [],
    ...overrides,
  };
};

export const getFormSections = (form) => {
  if (!form) return [];
  return Array.isArray(form.sections) ? form.sections : [];
};

export const getFormFields = (form) =>
  getFormSections(form).flatMap((section) => section.fields || []);

export const createElement = (type = "text", overrides = {}) => {
  const base = {
    id: createId("element"),
    type,
    name: type,
    content: "",
    mode: "auto",
    position: createPosition(),
    connectedFormId: "",
    action: createAction(),
    styles: {
      color: "var(--theme-text)",
      backgroundColor: "",
      borderRadius: "16px",
      fontSize: "",
      fontWeight: "",
      textAlign: "left",
      lineHeight: "",
      alignSelf: "auto",
    },
  };

  const presets = {
    heading: {
      name: factoryCopy.elements.heading.name,
      content: factoryCopy.elements.heading.content,
      styles: {
        ...base.styles,
        fontSize: "46px",
        fontWeight: "950",
        lineHeight: "1.04",
      },
    },
    text: {
      name: factoryCopy.elements.text.name,
      content: factoryCopy.elements.text.content,
      styles: {
        ...base.styles,
        color: "var(--theme-text-soft)",
        fontSize: "17px",
        lineHeight: "1.7",
      },
    },
    button: {
      name: factoryCopy.elements.button.name,
      content: factoryCopy.elements.button.content,
      action: createAction("goToPage"),
      styles: {
        ...base.styles,
        color: "var(--theme-text-inverse)",
        backgroundColor: "var(--theme-primary)",
        fontWeight: "900",
      },
    },
    image: {
      name: factoryCopy.elements.image.name,
      content: "",
      styles: {
        ...base.styles,
        borderRadius: "22px",
        alignSelf: "stretch",
      },
    },
    card: {
      name: factoryCopy.elements.card.name,
      carouselVariant: "cards",
      autoScroll: true,
      autoScrollMs: 4000,
      content: factoryCopy.elements.card.content,
      styles: {
        ...base.styles,
        backgroundColor: "var(--theme-surface)",
        borderRadius: "22px",
        alignSelf: "stretch",
        "--carousel-height": "340px",
      },
    },
    carousel: {
      name: factoryCopy.elements.carousel.name,
      carouselVariant: "lightswind",
      autoScroll: true,
      autoScrollMs: 4000,
      content: factoryCopy.elements.carousel.content,
      styles: {
        ...base.styles,
        backgroundColor: "var(--theme-surface)",
        borderRadius: "26px",
        alignSelf: "stretch",
        "--carousel-height": "410px",
      },
    },
    carouselCards: {
      name: factoryCopy.elements.carouselCards.name,
      carouselVariant: "cards",
      autoScroll: true,
      autoScrollMs: 4000,
      content: factoryCopy.elements.carouselCards.content,
      styles: {
        ...base.styles,
        backgroundColor: "var(--theme-surface)",
        borderRadius: "24px",
        alignSelf: "stretch",
        "--carousel-height": "340px",
      },
    },
    carouselSplit: {
      name: factoryCopy.elements.carouselSplit.name,
      carouselVariant: "split",
      autoScroll: true,
      autoScrollMs: 4000,
      content: factoryCopy.elements.carouselSplit.content,
      styles: {
        ...base.styles,
        backgroundColor: "var(--theme-surface)",
        borderRadius: "24px",
        alignSelf: "stretch",
        "--carousel-height": "360px",
      },
    },
    carouselSpotlight: {
      name: factoryCopy.elements.carouselSpotlight.name,
      carouselVariant: "spotlight",
      autoScroll: true,
      autoScrollMs: 4500,
      content: factoryCopy.elements.carouselSpotlight.content,
      styles: { ...base.styles, backgroundColor: "var(--theme-bg)", borderRadius: "30px", alignSelf: "stretch", "--carousel-height": "400px" },
    },
    carouselStack: {
      name: factoryCopy.elements.carouselStack.name,
      carouselVariant: "stack",
      autoScroll: true,
      autoScrollMs: 4000,
      content: factoryCopy.elements.carouselStack.content,
      styles: { ...base.styles, backgroundColor: "var(--theme-surface-2)", borderRadius: "30px", alignSelf: "stretch", "--carousel-height": "420px" },
    },
    carouselEditorial: {
      name: factoryCopy.elements.carouselEditorial.name,
      carouselVariant: "editorial",
      autoScroll: true,
      autoScrollMs: 5000,
      content: factoryCopy.elements.carouselEditorial.content,
      styles: { ...base.styles, backgroundColor: "var(--theme-bg-soft)", borderRadius: "8px", alignSelf: "stretch", "--carousel-height": "380px" },
    },
    circularGallery: {
      name: factoryCopy.elements.circularGallery.name,
      carouselVariant: "circular",
      autoScroll: true,
      autoScrollMs: 5000,
      content: factoryCopy.elements.circularGallery.content,
      styles: {
        ...base.styles,
        backgroundColor: "var(--theme-surface)",
        borderRadius: "26px",
        alignSelf: "stretch",
        "--carousel-height": "460px",
        "--gallery-depth": "360px",
      },
    },
    list: {
      name: factoryCopy.elements.list.name,
      content: factoryCopy.elements.list.items.join("\n"),
      listTitle: "",
      listStyle: "disc",
      listItems: factoryCopy.elements.list.items,
      styles: {
        ...base.styles,
        color: "var(--theme-text-soft)",
        backgroundColor: "var(--theme-surface)",
        borderRadius: "18px",
        alignSelf: "stretch",
      },
    },
    divider: {
      name: factoryCopy.elements.divider.name,
      content: "",
      styles: {
        ...base.styles,
        backgroundColor: "rgba(var(--theme-shadow-rgb), 0.16)",
        alignSelf: "stretch",
      },
    },
    embed: {
      name: factoryCopy.elements.embed.name,
      content: factoryCopy.elements.embed.content,
      styles: {
        ...base.styles,
        backgroundColor: "var(--theme-surface)",
        borderRadius: "18px",
        alignSelf: "stretch",
      },
    },
    metric: {
      name: factoryCopy.elements.metric.name,
      content: factoryCopy.elements.metric.content,
      metricColumns: 4,
      metrics: (factoryCopy.elements.metric.metrics || []).map((metric) => ({ ...metric })),
      styles: {
        ...base.styles,
        backgroundColor: "var(--theme-surface)",
        borderRadius: "22px",
        alignSelf: "stretch",
        metricTextColor: "#172b4d",
        metricSymbolColor: "#f1b84b",
      },
    },
    loginBlock: {
      name: factoryCopy.elements.loginBlock.name,
      content: factoryCopy.elements.loginBlock.content,
      auth: factoryCopy.elements.loginBlock.auth,
      styles: {
        ...base.styles,
        backgroundColor: "var(--theme-surface)",
        borderRadius: "24px",
        alignSelf: "stretch",
      },
    },
    registrationBlock: {
      name: factoryCopy.elements.registrationBlock.name,
      content: factoryCopy.elements.registrationBlock.content,
      auth: factoryCopy.elements.registrationBlock.auth,
      styles: {
        ...base.styles,
        backgroundColor: "var(--theme-surface)",
        borderRadius: "24px",
        alignSelf: "stretch",
      },
    },
    formBlock: {
      name: factoryCopy.elements.formBlock.name,
      content: factoryCopy.elements.formBlock.content,
      styles: {
        ...base.styles,
        backgroundColor: "var(--theme-surface)",
        borderRadius: "22px",
        alignSelf: "stretch",
      },
    },
    reservationBlock: {
      name: factoryCopy.elements.reservationBlock.name,
      content: factoryCopy.elements.reservationBlock.content,
      reservation: factoryCopy.elements.reservationBlock.reservation,
      styles: {
        ...base.styles,
        backgroundColor: "var(--theme-surface)",
        borderRadius: "22px",
        alignSelf: "stretch",
      },
    },
  };

  return {
    ...base,
    ...(presets[type] || {}),
    ...overrides,
    styles: {
      ...base.styles,
      ...(presets[type]?.styles || {}),
      ...(overrides.styles || {}),
    },
    action: {
      ...base.action,
      ...(presets[type]?.action || {}),
      ...(overrides.action || {}),
    },
  };
};

export const createColumn = (elements = [], overrides = {}) => ({
  id: createId("column"),
  name: factoryCopy.structure.column,
  layout: {
    align: "left",
  },
  elements,
  ...overrides,
});

export const createRow = (columns = [createColumn()], overrides = {}) => ({
  id: createId("row"),
  layout: {
    columns: String(columns.length),
    align: "center",
    gap: "medium",
  },
  columns,
  ...overrides,
});

export const createSection = ({
  name = factoryCopy.structure.section,
  mode = "auto",
  layout = {},
  rows = [createRow()],
  freeElements = [],
} = {}) => ({
  id: createId("section"),
  name,
  mode,
  layout: {
    width: "large",
    paddingY: "large",
    background: "transparent",
    minHeight: 560,
    ...layout,
  },
  rows,
  freeElements,
});

export const createPage = (name = factoryCopy.structure.page, sections = [], overrides = {}) => ({
  id: createId("page"),
  name,
  slug: name.toLowerCase() === "home" ? "/" : `/${slugify(name)}`,
  isDefault: name.toLowerCase() === "home",
  backgroundColor: "var(--theme-surface)",
  visibility: "public",
  showInNavigation: name.toLowerCase() === "home",
  pageType: "main",
  sections,
  ...overrides,
});

export const createWorkflow = (name = factoryCopy.structure.workflow, formId = "") => ({
  id: createId("workflow"),
  name,
  enabled: true,
  trigger: "formSubmitted",
  formId,
  steps: [
    {
      id: createId("workflowStep"),
      type: "saveResponse",
      label: factoryCopy.structure.workflowSteps.saveResponse.label,
      details: factoryCopy.structure.workflowSteps.saveResponse.details,
    },
    {
      id: createId("workflowStep"),
      type: "showMessage",
      label: factoryCopy.structure.workflowSteps.showMessage.label,
      details: factoryCopy.structure.workflowSteps.showMessage.details,
    },
  ],
});

export const createRole = (name = factoryCopy.structure.role, permissions = {}) => ({
  id: createId("role"),
  name,
  description: "",
  permissions: {
    ...defaultPermissions,
    ...permissions,
  },
});

export const createUser = (name = factoryCopy.structure.user, email = factoryCopy.structure.userEmail, roleId = "") => ({
  id: createId("user"),
  name,
  email,
  roleId,
  status: factoryCopy.structure.userStatus,
  lastSeen: factoryCopy.structure.lastSeen,
});

export const cloneWithNewIds = (value) => {
  if (Array.isArray(value)) return value.map(cloneWithNewIds);

  if (value && typeof value === "object") {
    const next = {};
    Object.entries(value).forEach(([key, item]) => {
      next[key] = key === "id" ? createId("copy") : cloneWithNewIds(item);
    });
    return next;
  }

  return value;
};

export const createProject = ({
  name = factoryCopy.structure.project,
  pages = [],
  forms = [],
  collections = [],
  workflows = [],
  roles = [],
  users = [],
  theme = defaultTheme,
  siteChrome = defaultSiteChrome,
} = {}) => ({
  id: createId("project"),
  name,
  status: "draft",
  activePageId: pages[0]?.id || "",
  activeFormId: forms[0]?.id || "",
  activeCollectionId: collections[0]?.id || "",
  activeWorkflowId: workflows[0]?.id || "",
  activeRoleId: roles[0]?.id || "",
  siteChrome,
  theme,
  pages,
  forms,
  collections,
  workflows,
  roles,
  users,
  publish: {
    environment: "local",
    lastSavedAt: "",
    lastPublishedAt: "",
  },
});
