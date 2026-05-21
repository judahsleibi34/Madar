import { createId, slugify, friendlyQuestionTypes } from "./PageBuilder.constants";

export const createPosition = () => ({
  desktop: { x: 48, y: 48, width: 360, height: 90 },
  tablet: { x: 36, y: 42, width: 320, height: 90 },
  mobile: { x: 22, y: 34, width: 300, height: 90 },
});

export const createQuestion = (label = "Untitled question", type = "shortText", overrides = {}) => ({
  id: createId("question"),
  label,
  type,
  required: false,
  helpText: "",
  placeholder: friendlyQuestionTypes.find((item) => item.id === type)?.placeholder || "",
  options: ["Option 1", "Option 2"],
  saveAs: slugify(label).replaceAll("-", "_"),
  ...overrides,
});

export const createFormSection = (title = "Section 1", elements = []) => ({
  id: createId("formSection"),
  title,
  description: "",
  collapsed: false,
  elements,
});

export const createForm = (title = "Untitled Form", questions = []) => {
  const defaultQuestions =
    questions.length > 0
      ? questions
      : [
          createQuestion("Full name", "shortText", { required: true }),
          createQuestion("Email", "email", { required: true }),
          createQuestion("Details", "paragraph"),
        ];

  return {
    id: createId("form"),
    title,
    description: "Use this form to collect information.",
    successMessage: "Thank you. Your response has been submitted.",
    sections: [createFormSection("Section 1", defaultQuestions)],
    responses: [],
  };
};

export const getFormSections = (form) => {
  if (!form) return [];

  if (Array.isArray(form.sections) && form.sections.length > 0) {
    return form.sections;
  }

  return [
    {
      id: "legacy_section",
      title: "Section 1",
      description: "",
      collapsed: false,
      elements: Array.isArray(form.questions) ? form.questions : [],
    },
  ];
};

export const getFormQuestions = (form) =>
  getFormSections(form).flatMap((section) => section.elements || []);

export const createAction = (type = "none", overrides = {}) => ({
  type,
  pageId: "",
  formId: "",
  url: "",
  message: "",
  status: "",
  ...overrides,
});

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
      color: "#1a2744",
      backgroundColor: "",
      borderRadius: "14px",
      fontSize: "",
      fontWeight: "",
      textAlign: "left",
      alignSelf: "auto",
      lineHeight: "",
    },
  };

  const presets = {
    heading: {
      name: "Heading",
      content: "Build your website and collect responses without code",
      styles: {
        ...base.styles,
        fontSize: "44px",
        fontWeight: "900",
        lineHeight: "1.08",
      },
    },
    text: {
      name: "Text",
      content:
        "Create pages, forms, responses, automations, users, and publishing flows in one guided builder.",
      styles: {
        ...base.styles,
        color: "#53627a",
        fontSize: "17px",
        lineHeight: "1.7",
      },
    },
    button: {
      name: "Button",
      content: "Get started",
      action: createAction("goToPage"),
      styles: {
        ...base.styles,
        color: "#ffffff",
        backgroundColor: "#8b2a1a",
        fontWeight: "900",
      },
    },
    image: {
      name: "Image",
      content:
        "https://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&auto=format&fit=crop",
      styles: {
        ...base.styles,
        borderRadius: "20px",
        alignSelf: "stretch",
      },
    },
    card: {
      name: "Card",
      content: "Starter card\nUse this for a service, instruction, offer, or dashboard card.",
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "20px",
        alignSelf: "stretch",
      },
    },
    formBlock: {
      name: "Form Block",
      content: "Connected Form",
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "20px",
        alignSelf: "stretch",
      },
    },
    responsesTable: {
      name: "Responses Table",
      content: "Responses",
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "20px",
        alignSelf: "stretch",
      },
    },
    metric: {
      name: "Metric",
      content: "Responses\n24",
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "20px",
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

export const createColumn = (elements = []) => ({
  id: createId("column"),
  name: "Column",
  layout: {
    align: "left",
  },
  elements,
});

export const createRow = (columns = [createColumn()]) => ({
  id: createId("row"),
  layout: {
    columns: String(columns.length),
    align: "center",
    gap: "medium",
  },
  columns,
});

export const createSection = ({
  name = "Section",
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

export const createPage = (name = "Home", sections = []) => ({
  id: createId("page"),
  name,
  slug: name.toLowerCase() === "home" ? "/" : `/${slugify(name)}`,
  backgroundColor: "#ffffff",
  sections,
});

export const createAutomation = (name = "After form submit", formId = "") => ({
  id: createId("automation"),
  name,
  trigger: "formSubmitted",
  formId,
  enabled: true,
  steps: [
    {
      id: createId("step"),
      type: "saveResponse",
      label: "Save response",
      details: "Store answers in Responses.",
    },
    {
      id: createId("step"),
      type: "showMessage",
      label: "Show success message",
      details: "Show the form success message.",
    },
  ],
});

export const createRole = (name, permissions = {}) => ({
  id: createId("role"),
  name,
  description: "",
  permissions: {
    viewPages: true,
    submitForms: true,
    viewResponses: false,
    approveResponses: false,
    editPages: false,
    editForms: false,
    manageUsers: false,
    publish: false,
    ...permissions,
  },
});

export const cloneWithNewIds = (value) => {
  const copy = JSON.parse(JSON.stringify(value));

  const walk = (node) => {
    if (!node || typeof node !== "object") return;

    if (typeof node.id === "string") {
      const prefix = node.id.split("_")[0] || "id";
      node.id = createId(prefix);
    }

    Object.values(node).forEach(walk);
  };

  walk(copy);
  return copy;
};