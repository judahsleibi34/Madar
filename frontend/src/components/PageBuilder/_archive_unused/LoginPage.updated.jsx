import { defaultSiteChrome } from "./PageBuilder.constants";
import {
  createField,
  createCollection,
  createForm,
  createElement,
  createColumn,
  createRow,
  createSection,
  createPage,
  createWorkflow,
  createRole,
  createUser,
  createProject,
} from "./PageBuilder.factories";

export const heroSection = () =>
  createSection({
    name: "Hero",
    rows: [
      createRow([
        createColumn([
          createElement("heading"),
          createElement("text"),
          createElement("button", { content: "Fill the form" }),
        ]),
        createColumn([
          createElement("card", {
            content:
              "Madar App Builder\nPages, forms, data, workflows, users, and publishing in one front-end builder.",
          }),
        ]),
      ]),
    ],
  });

export const formSection = (formId = "") =>
  createSection({
    name: "Form Section",
    layout: {
      width: "medium",
      paddingY: "large",
      background: "#ffffff",
    },
    rows: [
      createRow([
        createColumn([
          createElement("heading", {
            content: "Submit your information",
            styles: { fontSize: "34px" },
          }),
          createElement("formBlock", {
            connectedFormId: formId,
          }),
        ]),
      ]),
    ],
  });

export const responsesSection = (formId = "") =>
  createSection({
    name: "Responses Overview",
    layout: {
      width: "large",
      paddingY: "medium",
      background: "#ffffff",
    },
    rows: [
      createRow([
        createColumn([
          createElement("heading", {
            content: "Responses",
            styles: { fontSize: "34px" },
          }),
          createElement("responsesTable", {
            connectedFormId: formId,
          }),
        ]),
      ]),
    ],
  });

export const loginSection = () =>
  createSection({
    name: "Login Section",
    layout: {
      width: "small",
      paddingY: "large",
      background: "#fbfaf8",
    },
    rows: [
      createRow([
        createColumn([
          createElement("heading", {
            content: "Login to your account",
            styles: {
              fontSize: "34px",
              textAlign: "center",
              alignSelf: "stretch",
            },
          }),
          createElement("text", {
            content:
              "Access your private dashboard, submissions, reports, and internal tools.",
            styles: {
              textAlign: "center",
              alignSelf: "stretch",
            },
          }),
          createElement("card", {
            name: "Login Form Card",
            content: "Email address\nPassword\nLogin",
            styles: {
              backgroundColor: "#ffffff",
              borderRadius: "24px",
              alignSelf: "stretch",
            },
          }),
        ]),
      ]),
    ],
  });

export const metricsSection = () =>
  createSection({
    name: "Metrics",
    layout: { paddingY: "medium", background: "#fbfaf8" },
    rows: [
      createRow([
        createColumn([createElement("metric", { content: "Total Responses\n128" })]),
        createColumn([createElement("metric", { content: "Pending\n24" })]),
        createColumn([createElement("metric", { content: "Approved\n86" })]),
        createColumn([createElement("metric", { content: "Rejected\n18" })]),
      ]),
    ],
  });

export const freeCanvasSection = () =>
  createSection({
    name: "Free Canvas",
    mode: "free",
    layout: {
      width: "large",
      paddingY: "none",
      background: "#ffffff",
      minHeight: 560,
    },
    rows: [],
    freeElements: [
      createElement("heading", {
        mode: "free",
        content: "Free canvas section",
        position: {
          desktop: { x: 60, y: 70, width: 520, height: 90 },
          tablet: { x: 40, y: 60, width: 440, height: 90 },
          mobile: { x: 24, y: 50, width: 300, height: 90 },
        },
      }),
      createElement("text", {
        mode: "free",
        content: "Use free canvas only when you need exact positioning. Auto layout is safer for responsive pages.",
        position: {
          desktop: { x: 60, y: 170, width: 520, height: 110 },
          tablet: { x: 40, y: 160, width: 440, height: 110 },
          mobile: { x: 24, y: 150, width: 300, height: 120 },
        },
      }),
    ],
  });

export const sectionLibrary = [
  { id: "hero", title: "Hero Section", category: "Website", description: "Headline, text, button, and card.", create: heroSection },
  { id: "login", title: "Login Section", category: "Auth", description: "Login page block for private/internal website areas.", create: loginSection },
  { id: "form", title: "Form Section", category: "Forms", description: "Place the active form on the page.", create: formSection },
  { id: "responses", title: "Responses Table", category: "Data", description: "Show saved responses.", create: responsesSection },
  { id: "metrics", title: "Metrics Section", category: "Dashboard", description: "Counters for responses and statuses.", create: metricsSection },
  { id: "free", title: "Free Canvas", category: "Advanced", description: "Drag-anywhere design section.", create: freeCanvasSection },
];

const createBaseRolesAndUsers = () => {
  const admin = createRole("Admin", {
    editPages: true,
    editTheme: true,
    useFreeCanvas: true,
    editCollections: true,
    viewResponses: true,
    exportData: true,
    editWorkflows: true,
    approveResponses: true,
    manageUsers: true,
    publish: true,
  });

  const editor = createRole("Editor", {
    editPages: true,
    editTheme: true,
    editCollections: true,
    viewResponses: true,
    editWorkflows: true,
  });

  const reviewer = createRole("Reviewer", {
    viewResponses: true,
    approveResponses: true,
  });

  return {
    roles: [admin, editor, reviewer],
    users: [
      createUser("You", "admin@madar.local", admin.id),
      createUser("Content Editor", "editor@madar.local", editor.id),
      createUser("Reviewer", "reviewer@madar.local", reviewer.id),
    ],
  };
};

export const buildStarterProject = (starterId = "website") => {
  const common = createBaseRolesAndUsers();

  if (starterId === "requests") {
    const collection = createCollection("Requests", [
      createField("Full name", "shortText", { required: true }),
      createField("Request type", "dropdown", {
        required: true,
        options: ["HR", "Finance", "Procurement", "General"],
      }),
      createField("Amount", "money"),
      createField("Details", "paragraph", { required: true }),
      createField("Status", "status", { options: ["Pending", "Approved", "Rejected"], defaultValue: "Pending" }),
    ]);

    const form = createForm("Request Form", collection.fields, {
      connectedCollectionId: collection.id,
    });

    const pages = [
      createPage("Portal Home", [heroSection(), metricsSection()]),
      createPage("Submit Request", [formSection(form.id)]),
      createPage("Review Responses", [responsesSection(form.id)]),
    ];

    return createProject({
      name: "Request / Approval Portal",
      pages,
      forms: [form],
      collections: [collection],
      workflows: [createWorkflow("After request is submitted", form.id)],
      roles: common.roles,
      users: common.users,
    });
  }

  if (starterId === "reports") {
    const collection = createCollection("Activity Reports", [
      createField("Activity title", "shortText", { required: true }),
      createField("Project", "shortText"),
      createField("Date", "date", { required: true }),
      createField("Participants", "number"),
      createField("Notes", "paragraph"),
      createField("Status", "status", { options: ["Draft", "Submitted", "Reviewed"], defaultValue: "Draft" }),
    ]);

    const form = createForm("Activity Report Form", collection.fields, {
      connectedCollectionId: collection.id,
    });

    const pages = [
      createPage("Monitoring Dashboard", [heroSection(), metricsSection()]),
      createPage("Submit Report", [formSection(form.id)]),
      createPage("Reports", [responsesSection(form.id)]),
    ];

    return createProject({
      name: "Monitoring / Reporting Hub",
      pages,
      forms: [form],
      collections: [collection],
      workflows: [createWorkflow("After report is submitted", form.id)],
      roles: common.roles,
      users: common.users,
    });
  }

  if (starterId === "orders") {
    const collection = createCollection("Orders", [
      createField("Customer name", "shortText", { required: true }),
      createField("Phone number", "phone", { required: true }),
      createField("Order details", "paragraph", { required: true }),
      createField("Payment amount", "money"),
      createField("Order status", "status", {
        options: ["New", "Processing", "Ready", "Completed", "Cancelled"],
        defaultValue: "New",
      }),
    ]);

    const form = createForm("Order Form", collection.fields, {
      connectedCollectionId: collection.id,
    });

    const pages = [
      createPage("Store Home", [heroSection()]),
      createPage("Place Order", [formSection(form.id)]),
      createPage("Orders", [metricsSection(), responsesSection(form.id)]),
    ];

    return createProject({
      name: "Orders / Booking System",
      pages,
      forms: [form],
      collections: [collection],
      workflows: [createWorkflow("After order is submitted", form.id)],
      roles: common.roles,
      users: common.users,
    });
  }

  if (starterId === "blank") {
    const collection = createCollection("Items");
    const form = createForm("Untitled Form", [createField("Question 1", "shortText")], {
      connectedCollectionId: collection.id,
    });

    return createProject({
      name: "Blank Custom System",
      pages: [createPage("Home", [heroSection()])],
      forms: [form],
      collections: [collection],
      workflows: [createWorkflow("After form is submitted", form.id)],
      roles: common.roles,
      users: common.users,
    });
  }

  const collection = createCollection("Contacts", [
    createField("Full name", "shortText", { required: true }),
    createField("Email", "email", { required: true }),
    createField("Message", "paragraph"),
    createField("Status", "status", { options: ["New", "Contacted", "Closed"], defaultValue: "New" }),
  ]);

  const form = createForm("Contact Form", collection.fields, {
    connectedCollectionId: collection.id,
  });

  return createProject({
    name: "Website + Contact Form",
    siteChrome: {
    ...defaultSiteChrome,
    headerButtonLabel: "Login",
    footerShopLinks: "Home\nLogin\nContact\nResponses",
    },
    pages: [
      createPage("Home", [heroSection(), formSection(form.id)]),
      createPage("Responses", [responsesSection(form.id)]),
    ],
    forms: [form],
    collections: [collection],
    workflows: [createWorkflow("After contact form is submitted", form.id)],
    roles: common.roles,
    users: common.users,
  });
};

export const createInitialProject = () => buildStarterProject("requests");
