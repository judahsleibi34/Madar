import { createId, slugify, defaultPermissions, defaultTheme, defaultSiteChrome, fieldTypes } from "./PageBuilder.constants";

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

export const createField = (label = "Untitled field", type = "shortText", overrides = {}) => {
  const meta = fieldTypes.find((field) => field.id === type);
  const choiceDefaults = ["dropdown", "radio", "checkboxes", "status"].includes(type)
    ? ["Option 1", "Option 2"]
    : [];

  return {
    id: createId("field"),
    label,
    type,
    key: slugify(label).replaceAll("-", "_"),
    required: false,
    helpText: "",
    placeholder: meta?.label || "",
    options: choiceDefaults,
    defaultValue: "",
    scaleMin: 1,
    scaleMax: 5,
    scaleMinLabel: "Low",
    scaleMaxLabel: "High",
    maxRating: 5,
    width: "full",
    quizCorrectAnswer: type === "checkboxes" ? [] : "",
    quizPoints: 1,
    ...overrides,
  };
};

export const createCollection = (name = "Requests", fields = []) => ({
  id: createId("collection"),
  name,
  key: slugify(name).replaceAll("-", "_"),
  description: "Front-end collection model. Connect this to your backend later.",
  fields:
    fields.length > 0
      ? fields
      : [
          createField("Title", "shortText", { required: true }),
          createField("Status", "status", {
            options: ["New", "Pending", "Approved", "Rejected"],
            defaultValue: "New",
          }),
          createField("Created by", "shortText"),
        ],
  records: [],
});

export const createFormSection = (title = "Section 1", fields = []) => ({
  id: createId("formSection"),
  title,
  description: "",
  collapsed: false,
  fields,
});

export const createForm = (title = "Untitled Form", fields = [], overrides = {}) => {
  const defaultFields =
    fields.length > 0
      ? fields
      : [
          createField("Full name", "shortText", { required: true }),
          createField("Email", "email", { required: true }),
          createField("Details", "paragraph"),
        ];

  return {
    id: createId("form"),
    title,
    description: "Use this form to collect information.",
    successMessage: "Thank you. Your response has been submitted.",
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
    sections: [createFormSection("Section 1", defaultFields)],
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
      color: "#1a2744",
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
      name: "Heading",
      content: "Build your business app without code",
      styles: {
        ...base.styles,
        fontSize: "46px",
        fontWeight: "950",
        lineHeight: "1.04",
      },
    },
    text: {
      name: "Text",
      content:
        "Design pages, collect responses, manage roles, prototype workflows, and prepare everything for backend integration later.",
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
        borderRadius: "22px",
        alignSelf: "stretch",
      },
    },
    card: {
      name: "Card",
      content: "Starter card\nUse this for services, offers, instructions, or dashboard blocks.",
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "22px",
        alignSelf: "stretch",
      },
    },
    carousel: {
      name: "Lightswind Carousel",
      carouselVariant: "lightswind",
      autoScroll: true,
      autoScrollMs: 4000,
      content:
        "Launch faster\nShowcase products, services, or featured content with a clean carousel.\nhttps://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&auto=format&fit=crop\n\nCollect attention\nUse large visuals, concise copy, and simple navigation for high-impact sections.\nhttps://images.unsplash.com/photo-1497215728101-856f4ea42174?w=1200&auto=format&fit=crop\n\nStay flexible\nEdit slide text and image URLs directly from the Page Builder inspector.\nhttps://images.unsplash.com/photo-1556761175-b413da4baf72?w=1200&auto=format&fit=crop",
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "26px",
        alignSelf: "stretch",
        "--carousel-height": "410px",
      },
    },
    carouselCards: {
      name: "Card Carousel",
      carouselVariant: "cards",
      autoScroll: true,
      autoScrollMs: 4000,
      content:
        "Featured service\nPresent one offer at a time with a clean card and supporting image.\nhttps://images.unsplash.com/photo-1556761175-5973dc0f32e7?w=1200&auto=format&fit=crop\n\nProduct highlight\nUse this variant for offers, collections, packages, or case studies.\nhttps://images.unsplash.com/photo-1497215728101-856f4ea42174?w=1200&auto=format&fit=crop\n\nCustomer story\nMove through compact slides without taking over the full page section.\nhttps://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=1200&auto=format&fit=crop",
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "24px",
        alignSelf: "stretch",
        "--carousel-height": "340px",
      },
    },
    carouselSplit: {
      name: "Split Carousel",
      carouselVariant: "split",
      autoScroll: true,
      autoScrollMs: 4000,
      content:
        "Strategy and execution\nPair focused text with a strong image area for services or announcements.\nhttps://images.unsplash.com/photo-1552664730-d307ca884978?w=1200&auto=format&fit=crop\n\nBuilt for teams\nShow process steps, onboarding, or operational features in a balanced layout.\nhttps://images.unsplash.com/photo-1556761175-b413da4baf72?w=1200&auto=format&fit=crop\n\nReady to publish\nUse the same slide format: title, description, and image URL.\nhttps://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&auto=format&fit=crop",
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "24px",
        alignSelf: "stretch",
        "--carousel-height": "360px",
      },
    },
    circularGallery: {
      name: "Circular Gallery",
      carouselVariant: "circular",
      autoScroll: true,
      autoScrollMs: 5000,
      content:
        "Studio workspace\nA warm workspace for planning and operations.\nhttps://images.unsplash.com/photo-1497366754035-f200968a6e72?w=1200&auto=format&fit=crop\n\nTeam session\nPeople collaborating around a product launch.\nhttps://images.unsplash.com/photo-1552664730-d307ca884978?w=1200&auto=format&fit=crop\n\nProduct desk\nClean desk scene with business tools.\nhttps://images.unsplash.com/photo-1497215728101-856f4ea42174?w=1200&auto=format&fit=crop\n\nService meeting\nClient service conversation in progress.\nhttps://images.unsplash.com/photo-1521737604893-d14cc237f11d?w=1200&auto=format&fit=crop\n\nAnalytics view\nDashboard and operations review moment.\nhttps://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1200&auto=format&fit=crop\n\nLaunch planning\nPlanning board for growth and execution.\nhttps://images.unsplash.com/photo-1556761175-b413da4baf72?w=1200&auto=format&fit=crop",
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "26px",
        alignSelf: "stretch",
        "--carousel-height": "460px",
        "--gallery-depth": "360px",
      },
    },
    list: {
      name: "List",
      content: "First item\nSecond item\nThird item",
      styles: {
        ...base.styles,
        color: "#53627a",
        backgroundColor: "#ffffff",
        borderRadius: "18px",
        alignSelf: "stretch",
      },
    },
    divider: {
      name: "Divider",
      content: "",
      styles: {
        ...base.styles,
        backgroundColor: "rgba(26, 39, 68, 0.16)",
        alignSelf: "stretch",
      },
    },
    embed: {
      name: "Embed",
      content: "https://example.com",
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "18px",
        alignSelf: "stretch",
      },
    },
    metric: {
      name: "Metric",
      content: "Total Requests\n128",
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "22px",
        alignSelf: "stretch",
      },
    },
    loginBlock: {
      name: "Login",
      content: "Log in\nAccess your account and continue to your workspace.\nLog in",
      auth: {
        title: "Log in",
        subtitle: "Access your account and continue to your workspace.",
        buttonText: "Log in",
        switchText: "Don't have an account?",
        switchActionText: "Create account",
      },
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "24px",
        alignSelf: "stretch",
      },
    },
    registrationBlock: {
      name: "Registration",
      content:
        "Register\nCreate an account to save requests, reservations, and private activity.\nCreate Account",
      auth: {
        title: "Register",
        subtitle: "Create an account to save requests, reservations, and private activity.",
        buttonText: "Create Account",
        switchText: "Already registered?",
        switchActionText: "Log in",
      },
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "24px",
        alignSelf: "stretch",
      },
    },
    formBlock: {
      name: "Form Block",
      content: "Connected Form",
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "22px",
        alignSelf: "stretch",
      },
    },
    reservationBlock: {
      name: "Reservation",
      content:
        "Book a reservation\nChoose a service, date, and time. We will confirm availability with you.\nConsultation\nService appointment\nTable reservation",
      reservation: {
        title: "Book a reservation",
        description: "Choose a service, date, and time. We will confirm availability with you.",
        services: ["Consultation", "Service appointment", "Table reservation"],
        fields: ["name", "contact", "service", "date", "time", "guests", "notes"],
        submitLabel: "Request reservation",
      },
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
        borderRadius: "22px",
        alignSelf: "stretch",
      },
    },
    responsesTable: {
      name: "Responses Table",
      content: "Responses",
      styles: {
        ...base.styles,
        backgroundColor: "#ffffff",
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
  name: "Column",
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

export const createPage = (name = "Home", sections = [], overrides = {}) => ({
  id: createId("page"),
  name,
  slug: name.toLowerCase() === "home" ? "/" : `/${slugify(name)}`,
  backgroundColor: "#ffffff",
  visibility: "public",
  showInNavigation: true,
  pageType: "main",
  sections,
  ...overrides,
});

export const createWorkflow = (name = "After form submit", formId = "") => ({
  id: createId("workflow"),
  name,
  enabled: true,
  trigger: "formSubmitted",
  formId,
  steps: [
    {
      id: createId("workflowStep"),
      type: "saveResponse",
      label: "Save response",
      details: "Store submitted values in front-end state.",
    },
    {
      id: createId("workflowStep"),
      type: "showMessage",
      label: "Show success message",
      details: "Display the form success message.",
    },
  ],
});

export const createRole = (name = "Viewer", permissions = {}) => ({
  id: createId("role"),
  name,
  description: "",
  permissions: {
    ...defaultPermissions,
    ...permissions,
  },
});

export const createUser = (name = "Team Member", email = "member@example.com", roleId = "") => ({
  id: createId("user"),
  name,
  email,
  roleId,
  status: "Active",
  lastSeen: "Just now",
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
  name = "Madar App Builder",
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
