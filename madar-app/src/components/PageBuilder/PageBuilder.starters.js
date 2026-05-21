import { createId, defaultSiteChrome } from "./PageBuilder.constants";
import {
  createQuestion,
  createForm,
  createElement,
  createColumn,
  createRow,
  createSection,
  createPage,
  createAutomation,
  createRole,
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
              "Guided builder\nPages, forms, responses, automations, users, and publishing.",
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

export const metricsSection = () =>
  createSection({
    name: "Metrics",
    layout: { paddingY: "medium" },
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
        content:
          "Use free canvas only when you need full design freedom. Auto layout is safer for responsive pages.",
        position: {
          desktop: { x: 60, y: 170, width: 520, height: 110 },
          tablet: { x: 40, y: 160, width: 440, height: 110 },
          mobile: { x: 24, y: 150, width: 300, height: 120 },
        },
      }),
    ],
  });

export const sectionLibrary = [
  {
    id: "hero",
    title: "Hero Section",
    category: "Website",
    description: "Headline, text, button, and card.",
    create: heroSection,
  },
  {
    id: "form",
    title: "Form Section",
    category: "Forms",
    description: "Place a selected form on a page.",
    create: formSection,
  },
  {
    id: "responses",
    title: "Responses Table",
    category: "Responses",
    description: "Show saved answers in a table.",
    create: responsesSection,
  },
  {
    id: "metrics",
    title: "Metrics Section",
    category: "Dashboard",
    description: "Counters for responses and statuses.",
    create: metricsSection,
  },
  {
    id: "free",
    title: "Free Canvas",
    category: "Advanced",
    description: "Drag-anywhere design section.",
    create: freeCanvasSection,
  },
];

export const buildStarterProject = (starterId) => {
  if (starterId === "requests") {
    const form = createForm("Request Form", [
      createQuestion("Full name", "shortText", { required: true }),
      createQuestion("Request type", "dropdown", {
        options: ["HR", "Finance", "Procurement", "General"],
        required: true,
      }),
      createQuestion("Amount", "money"),
      createQuestion("Details", "paragraph", { required: true }),
      createQuestion("Status", "status", { options: ["Pending", "Approved", "Rejected"] }),
    ]);

    return {
      pages: [
        createPage("Portal Home", [heroSection(), metricsSection()]),
        createPage("Submit Request", [formSection(form.id)]),
        createPage("Review Responses", [responsesSection(form.id)]),
      ],
      forms: [form],
      automations: [createAutomation("After request is submitted", form.id)],
      roles: [
        createRole("Submitter"),
        createRole("Reviewer", { viewResponses: true, approveResponses: true }),
        createRole("Admin", {
          viewResponses: true,
          approveResponses: true,
          editPages: true,
          editForms: true,
          manageUsers: true,
          publish: true,
        }),
      ],
    };
  }

  if (starterId === "reports") {
    const form = createForm("Activity Report Form", [
      createQuestion("Activity title", "shortText", { required: true }),
      createQuestion("Project", "shortText"),
      createQuestion("Date", "date", { required: true }),
      createQuestion("Participants", "number"),
      createQuestion("Notes", "paragraph"),
      createQuestion("Status", "status", { options: ["Draft", "Submitted", "Reviewed"] }),
    ]);

    return {
      pages: [
        createPage("Monitoring Dashboard", [heroSection(), metricsSection()]),
        createPage("Submit Report", [formSection(form.id)]),
        createPage("Reports", [responsesSection(form.id)]),
      ],
      forms: [form],
      automations: [createAutomation("After report is submitted", form.id)],
      roles: [
        createRole("Field User"),
        createRole("Coordinator", { viewResponses: true }),
        createRole("Admin", {
          viewResponses: true,
          approveResponses: true,
          editPages: true,
          editForms: true,
          manageUsers: true,
          publish: true,
        }),
      ],
    };
  }

  if (starterId === "orders") {
    const form = createForm("Order Form", [
      createQuestion("Customer name", "shortText", { required: true }),
      createQuestion("Phone number", "phone", { required: true }),
      createQuestion("Order details", "paragraph", { required: true }),
      createQuestion("Payment amount", "money"),
      createQuestion("Order status", "status", {
        options: ["New", "Processing", "Ready", "Completed", "Cancelled"],
      }),
    ]);

    return {
      pages: [
        createPage("Store Home", [heroSection()]),
        createPage("Place Order", [formSection(form.id)]),
        createPage("Orders", [metricsSection(), responsesSection(form.id)]),
      ],
      forms: [form],
      automations: [createAutomation("After order is submitted", form.id)],
      roles: [
        createRole("Customer"),
        createRole("Staff", { viewResponses: true }),
        createRole("Owner", {
          viewResponses: true,
          approveResponses: true,
          editPages: true,
          editForms: true,
          manageUsers: true,
          publish: true,
        }),
      ],
    };
  }

  if (starterId === "blank") {
    const form = createForm("Untitled Form", [createQuestion("Question 1", "shortText")]);

    return {
      pages: [createPage("Home", [heroSection()])],
      forms: [form],
      automations: [createAutomation("After form is submitted", form.id)],
      roles: [
        createRole("Visitor"),
        createRole("Admin", {
          viewResponses: true,
          editPages: true,
          editForms: true,
          manageUsers: true,
          publish: true,
        }),
      ],
    };
  }

  const form = createForm("Contact Form", [
    createQuestion("Full name", "shortText", { required: true }),
    createQuestion("Email", "email", { required: true }),
    createQuestion("Message", "paragraph", { required: true }),
  ]);

  return {
    pages: [
      createPage("Home", [heroSection()]),
      createPage("Contact", [formSection(form.id)]),
    ],
    forms: [form],
    automations: [createAutomation("After contact form is submitted", form.id)],
    roles: [
      createRole("Visitor"),
      createRole("Content Manager", {
        viewResponses: true,
        editPages: true,
        editForms: true,
        publish: true,
      }),
    ],
  };
};

export const createInitialProject = () => {
  const starter = buildStarterProject("website");

  return {
    id: createId("project"),
    name: "Madar Builder",
    description: "Guided no-code builder for pages, forms, responses, and automations.",
    activePageId: starter.pages[0].id,
    activeFormId: starter.forms[0].id,
    status: "draft",
    pages: starter.pages,
    forms: starter.forms,
    automations: starter.automations,
    roles: starter.roles,
    publish: {
      lastSavedAt: "",
      lastPublishedAt: "",
      seoTitle: "Madar Builder",
      seoDescription: "No-code website and form system.",
    },
    siteChrome: {
      showHeader: true,
      showFooter: true,
      ...defaultSiteChrome,
      logoUrl: "",
      headerAlign: "center",
      headerButtonLabel: "Contact",
      footerStoreName: "Your Website",
      footerShopTitle: "Shop",
      footerShopLinks: "All Products\nAll Categories",
      footerHelpTitle: "Help",
      footerHelpLinks: "Our Policies\nAbout Us\nTrack Your Orders",
      footerSocialLinks: "Facebook\nLinkedIn\nX\nInstagram",
      footerPaymentMethods: "Visa\nMastercard\nApple Pay\nGoogle Pay",
      footerLanguageLabel: "AR",
      madarLink: "/",
    },
  };
};