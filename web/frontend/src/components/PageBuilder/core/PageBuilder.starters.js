import { defaultSiteChrome, PILATES_DEMO_THEME } from "./PageBuilder.constants";
export { PILATES_DEMO_THEME } from "./PageBuilder.constants";
import { getStarterContent } from "../../../content/pageBuilder";
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

const starterText = getStarterContent("en");

export const heroSection = () =>
  createSection({
    name: "Hero",
    rows: [
      createRow([
        createColumn([
          createElement("heading"),
          createElement("text"),
          createElement("button", { content: starterText.defaults.heroButton }),
        ]),
        createColumn([
          createElement("card", {
            content:
              starterText.defaults.heroCard,
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
      background: "var(--theme-surface)",
    },
    rows: [
      createRow([
        createColumn([
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
      background: "var(--theme-surface)",
    },
    rows: [
      createRow([
        createColumn([
          createElement("heading", {
            content: starterText.defaults.responsesHeading,
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
      width: "full",
      paddingY: "large",
      background: "var(--theme-surface-2)",
    },
    rows: [
      createRow([
        createColumn([
          createElement("heading", {
            content: starterText.defaults.loginHeading,
            styles: {
              fontSize: "34px",
              textAlign: "center",
              alignSelf: "stretch",
            },
          }),
          createElement("text", {
            content:
              starterText.defaults.loginText,
            styles: {
              textAlign: "center",
              alignSelf: "stretch",
            },
          }),
          createElement("loginBlock", {
            name: "Login Form Card",
            content: starterText.defaults.loginCard,
            auth: {
              title: starterText.defaults.loginHeading,
              subtitle: starterText.defaults.loginText,
              buttonText: "Login",
              switchText: "",
              switchActionText: "",
            },
            styles: {
              backgroundColor: "var(--theme-surface)",
              borderRadius: "24px",
              alignSelf: "stretch",
            },
          }),
        ]),
      ]),
    ],
  });

export const createBlankCanvasSection = () => ({
  ...createSection({
    name: "Page Canvas",
    mode: "direct",
    layout: {
      width: "full",
      paddingY: "none",
      background: "transparent",
      minHeight: 720,
      minHeightByViewport: {
        desktop: 720,
        tablet: 720,
        mobile: 720,
      },
    },
    rows: [],
    freeElements: [],
  }),
  isPageCanvas: true,
});

export const createBlankWorkspaceProject = () =>
  createProject({
    name: "Untitled Site",
    pages: [
      createPage("Home", [createBlankCanvasSection()], {
        canvasLayoutVersion: 1,
      }),
    ],
    forms: [],
    collections: [],
    workflows: [],
    roles: [],
    users: [],
  });

export const metricsSection = () =>
  createSection({
    name: "Metrics",
    layout: { paddingY: "medium", background: "var(--theme-surface-2)" },
    rows: [
      createRow([
        createColumn([createElement("metric", { content: starterText.defaults.metrics.totalResponses })]),
        createColumn([createElement("metric", { content: starterText.defaults.metrics.pending })]),
        createColumn([createElement("metric", { content: starterText.defaults.metrics.approved })]),
        createColumn([createElement("metric", { content: starterText.defaults.metrics.rejected })]),
      ]),
    ],
  });

export const showcaseHeroSection = (formId = "") =>
  createSection({
    name: "Showcase Hero",
    layout: {
      width: "large",
      paddingY: "large",
      background: "var(--theme-surface-2)",
      minHeight: 560,
    },
    rows: [
      createRow([
        createColumn([
          createElement("heading", {
            content: "Build, launch, and manage a complete service portal",
            styles: { fontSize: "54px", lineHeight: "1.02" },
          }),
          createElement("text", {
            content:
              "This default template shows the full builder: responsive pages, rich content blocks, forms, saved responses, dashboards, bookings, auth screens, and publishing controls.",
          }),
          createElement("button", {
            content: "Start a request",
            connectedFormId: formId,
          }),
        ]),
        createColumn([
          createElement("image", {
            name: "Hero Image",
            content:
              "https://images.unsplash.com/photo-1556761175-b413da4baf72?w=1400&auto=format&fit=crop",
            styles: {
              borderRadius: "28px",
              alignSelf: "stretch",
            },
          }),
        ]),
      ]),
    ],
  });

export const showcaseContentSection = () =>
  createSection({
    name: "Content Elements",
    layout: {
      width: "large",
      paddingY: "large",
      background: "var(--theme-surface)",
      minHeight: 520,
    },
    rows: [
      createRow([
        createColumn([
          createElement("heading", {
            content: "Content blocks for every screen",
            styles: { fontSize: "38px" },
          }),
          createElement("text", {
            content:
              "Use headings, paragraphs, buttons, images, cards, lists, dividers, and embeds to build public pages or internal tools.",
          }),
          createElement("button", { content: "Publish page" }),
          createElement("divider"),
          createElement("list", {
            content:
              "Responsive columns and sections\nReusable cards and media blocks\nConnected forms and response tables\nRole-based workspace controls",
          }),
        ]),
        createColumn([
          createElement("card", {
            content:
              "Service launch kit\nPackage your offer, intake form, booking flow, and data view in one page.",
          }),
          createElement("embed", {
            content: "https://www.youtube.com/embed/dQw4w9WgXcQ",
          }),
        ]),
      ]),
    ],
  });

export const showcaseCarouselSection = () =>
  createSection({
    name: "Card Carousel",
    layout: {
      width: "large",
      paddingY: "large",
      background: "var(--theme-surface-2)",
      minHeight: 500,
    },
    rows: [createRow([createColumn([createElement("carousel")])])],
  });

export const showcaseConnectedSection = (formId = "") =>
  createSection({
    name: "Connected Operations",
    layout: {
      width: "large",
      paddingY: "large",
      background: "var(--theme-surface)",
      minHeight: 720,
    },
    rows: [
      createRow([
        createColumn([
          createElement("heading", {
            content: "Collect, review, and act on data",
            styles: { fontSize: "38px" },
          }),
          createElement("text", {
            content:
              "Forms, reservations, response tables, metrics, and workflows can live beside your page content.",
          }),
          createElement("formBlock", {
            connectedFormId: formId,
          }),
        ]),
        createColumn([
          createElement("responsesTable", {
            connectedFormId: formId,
          }),
          createElement("reservationBlock"),
        ]),
      ]),
    ],
  });

export const showcaseAuthSection = () =>
  createSection({
    name: "Authentication Blocks",
    layout: {
      width: "large",
      paddingY: "large",
      background: "var(--theme-surface-2)",
      minHeight: 520,
    },
    rows: [
      createRow([
        createColumn([
          createElement("loginBlock"),
        ]),
        createColumn([
          createElement("registrationBlock"),
        ]),
      ]),
    ],
  });

const sectionCreators = {
  hero: heroSection,
  login: loginSection,
  form: formSection,
  metrics: metricsSection,
};

export const sectionLibrary = starterText.sectionLibrary.map((section) => ({
  ...section,
  create: sectionCreators[section.id],
}));

const createBaseRolesAndUsers = () => {
  const admin = createRole("Admin", {
    editPages: true,
    editTheme: true,
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

const industryHeroSection = ({
  title,
  description,
  cta = starterText.defaults.industryCta,
  imageUrl,
  formId = "",
}) =>
  createSection({
    name: "Hero",
    layout: {
      width: "large",
      paddingY: "large",
      background: "var(--theme-surface-2)",
      minHeight: 560,
    },
    rows: [
      createRow([
        createColumn([
          createElement("heading", {
            content: title,
            styles: { fontSize: "52px", lineHeight: "1.04" },
          }),
          createElement("text", {
            content: description,
          }),
          createElement("button", {
            content: cta,
            connectedFormId: formId,
          }),
        ]),
        createColumn([
          createElement("image", {
            name: "Hero Image",
            content: imageUrl,
            styles: {
              borderRadius: "28px",
              alignSelf: "stretch",
            },
          }),
        ]),
      ]),
    ],
  });

const industryCardsSection = ({ title, description, cards = [] }) =>
  createSection({
    name: "Highlights",
    layout: {
      width: "large",
      paddingY: "large",
      background: "var(--theme-surface)",
      minHeight: 520,
    },
    rows: [
      createRow([
        createColumn([
          createElement("heading", {
            content: title,
            styles: { fontSize: "38px", textAlign: "center", alignSelf: "stretch" },
          }),
          createElement("text", {
            content: description,
            styles: { textAlign: "center", alignSelf: "stretch" },
          }),
        ]),
      ]),
      createRow(
        cards.slice(0, 3).map((card) =>
          createColumn([
            createElement("card", {
              content: `${card.title}\n${card.description}`,
            }),
          ])
        )
      ),
    ],
  });

const industryOperationsSection = ({ formId, title, description }) =>
  createSection({
    name: "Operations Workspace",
    layout: {
      width: "large",
      paddingY: "large",
      background: "var(--theme-surface-2)",
      minHeight: 720,
    },
    rows: [
      createRow([
        createColumn([
          createElement("heading", {
            content: title,
            styles: { fontSize: "38px" },
          }),
          createElement("text", {
            content: description,
          }),
          createElement("formBlock", {
            connectedFormId: formId,
          }),
        ]),
        createColumn([
          createElement("responsesTable", {
            connectedFormId: formId,
          }),
          createElement("metric", {
            content: starterText.defaults.metrics.openItems,
          }),
          createElement("metric", {
            content: starterText.defaults.metrics.readyForReview,
          }),
        ]),
      ]),
    ],
  });

const clearStarterRecords = ({ form, collection }) => {
  form.responses = [];
  collection.records = [];
};

export const buildStarterProject = (starterId = "website") => {
  if (starterId === "pilates") {
    return buildPilatesDemoProject();
  }

  const common = createBaseRolesAndUsers();

  if (starterId === "showcase") {
    const fields = [
      createField("Full name", "shortText", { required: true }),
      createField("Email", "email", { required: true }),
      createField("Phone number", "shortText", { placeholder: "+972 50 123 4567" }),
      createField("Company website", "url"),
      createField("Request summary", "paragraph", { required: true }),
      createField("Department", "dropdown", {
        required: true,
        options: ["Sales", "Operations", "Finance", "Support"],
      }),
      createField("Priority", "dropdown", {
        options: ["Low", "Medium", "High"],
        defaultValue: "Medium",
      }),
      createField("Needed services", "checkboxes", {
        options: ["Website", "Forms", "Reports", "Automation"],
      }),
      createField("Approved to contact", "dropdown", {
        options: ["Yes", "No"],
      }),
      createField("Expected budget", "number", { placeholder: "Example: 7,500" }),
      createField("Team size", "number"),
      createField("Preferred date", "date"),
      createField("Preferred time", "time"),
      createField("Satisfaction target", "linearScale", {
        scaleMin: 1,
        scaleMax: 10,
        scaleMinLabel: "Basic",
        scaleMaxLabel: "Excellent",
      }),
      createField("Readiness rating", "rating", { maxRating: 5 }),
      createField("Attachment", "file"),
      createField("Status", "dropdown", {
        options: ["New", "In review", "Approved", "Delivered"],
        defaultValue: "New",
      }),
    ];

    const collection = createCollection("Builder Showcase Requests", fields);
    collection.description =
      "A complete sample data model that demonstrates every supported field type.";

    const form = createForm("Showcase Request Form", fields, {
      connectedCollectionId: collection.id,
      description:
        "Collect project requests, contact details, service needs, budget, dates, ratings, files, and workflow status.",
      successMessage: "Your request was received. The team can now review it in the workspace.",
    });

    clearStarterRecords({ form, collection });

    const pages = [
      createPage("Builder Demo", [
        showcaseHeroSection(form.id),
        metricsSection(),
        showcaseContentSection(),
        showcaseCarouselSection(),
        showcaseConnectedSection(form.id),
        showcaseAuthSection(),
      ]),
      createPage("Operations", [
        responsesSection(form.id),
        formSection(form.id),
        showcaseAuthSection(),
      ]),
    ];

    return createProject({
      name: "Madar Builder Demo",
      siteChrome: {
        ...defaultSiteChrome,
        brand: "Madar",
        headerButtonLabel: "Login",
        headerButtonHref: "Login",
        footerShopLinks: "Builder Demo\nOperations\nLogin",
        description:
          "A complete service portal template with forms, data, reports, booking, and workspace controls.",
      },
      pages,
      forms: [form],
      collections: [collection],
      workflows: [createWorkflow("After showcase request is submitted", form.id)],
      roles: common.roles,
      users: common.users,
    });
  }

  if (starterId === "cms") {
    const fields = [
      createField("Content title", "shortText", { required: true }),
      createField("Content type", "dropdown", {
        required: true,
        options: ["Article", "Landing page", "Resource", "Announcement"],
      }),
      createField("Owner", "shortText", { required: true }),
      createField("Target publish date", "date"),
      createField("Audience", "dropdown", {
        options: ["Public", "Customers", "Internal team", "Partners"],
      }),
      createField("Summary", "paragraph", { required: true }),
      createField("Status", "dropdown", {
        options: ["Draft", "In review", "Approved", "Published"],
        defaultValue: "Draft",
      }),
    ];

    const collection = createCollection("Content Pipeline", fields);
    collection.description = "Editorial content records with owner, audience, date, and status.";

    const form = createForm("Content Request Form", fields, {
      connectedCollectionId: collection.id,
      description: "Use this form to request, brief, and review new content.",
      successMessage: "Content request received. The editorial team can review it now.",
    });

    clearStarterRecords({
      form,
      collection,
    });

    const pages = [
      createPage("Content Hub", [
        industryHeroSection({
          title: "Plan, publish, and govern content in one workspace",
          description:
            "A CMS-style template for editorial teams that need intake, page planning, review status, records, and reusable publishing workflows.",
          cta: "Request content",
          formId: form.id,
          imageUrl:
            "https://images.unsplash.com/photo-1497366811353-6870744d04b2?w=1400&auto=format&fit=crop",
        }),
        industryCardsSection({
          title: "Designed for content operations",
          description: "Keep the public website and internal editorial work connected.",
          cards: [
            { title: "Editorial intake", description: "Capture new page, article, and resource requests with consistent metadata." },
            { title: "Review workflow", description: "Track drafts, approvals, and publishing readiness before content goes live." },
            { title: "Content records", description: "Store content briefs and decisions in a searchable collection." },
          ],
        }),
        industryOperationsSection({
          formId: form.id,
          title: "Content request workspace",
          description:
            "Review submitted briefs beside the request form, then assign ownership and update publishing status.",
        }),
      ]),
      createPage("Editorial Review", [responsesSection(form.id), formSection(form.id)]),
    ];

    return createProject({
      name: "CMS Content Hub",
      siteChrome: {
        ...defaultSiteChrome,
        brand: "Madar CMS",
        footerStoreName: "Madar CMS",
        footerShopLinks: "Content Hub\nEditorial Review\nLogin",
        description: "A CMS operations template for content intake, review, and publishing control.",
      },
      pages,
      forms: [form],
      collections: [collection],
      workflows: [createWorkflow("After content request is submitted", form.id)],
      roles: common.roles,
      users: common.users,
    });
  }

  if (starterId === "ecommerce") {
    const fields = [
      createField("Customer name", "shortText", { required: true }),
      createField("Email", "email", { required: true }),
      createField("Phone number", "shortText", { required: true, placeholder: "+972 50 123 4567" }),
      createField("Product or service", "dropdown", {
        required: true,
        options: ["Starter package", "Growth package", "Custom order", "Consultation"],
      }),
      createField("Quantity", "number"),
      createField("Delivery date", "date"),
      createField("Order notes", "paragraph"),
      createField("Order status", "dropdown", {
        options: ["New", "Confirmed", "Preparing", "Ready", "Completed"],
        defaultValue: "New",
      }),
    ];

    const collection = createCollection("Store Orders", fields);
    collection.description = "Commerce order records with customer, product, quantity, and status.";

    const form = createForm("Order Intake Form", fields, {
      connectedCollectionId: collection.id,
      description: "Collect product orders, customer details, delivery dates, and fulfillment notes.",
      successMessage: "Order received. The team can confirm availability and fulfillment next.",
    });

    clearStarterRecords({
      form,
      collection,
    });

    const pages = [
      createPage("Storefront", [
        industryHeroSection({
          title: "Sell products, capture orders, and track fulfillment",
          description:
            "A commerce template for lightweight storefronts, order requests, customer records, and operations teams that need clarity after checkout.",
          cta: "Place an order",
          formId: form.id,
          imageUrl:
            "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=1400&auto=format&fit=crop",
        }),
        industryCardsSection({
          title: "Everything a lean commerce flow needs",
          description: "Present offers, collect orders, and manage follow-up from the same builder.",
          cards: [
            { title: "Product offers", description: "Show packages, services, or collections with clear calls to action." },
            { title: "Order intake", description: "Capture customer details, requested products, notes, and delivery dates." },
            { title: "Fulfillment view", description: "Review new, confirmed, preparing, ready, and completed orders." },
          ],
        }),
        showcaseCarouselSection(),
        industryOperationsSection({
          formId: form.id,
          title: "Order management workspace",
          description:
            "Keep order details, responses, metrics, and fulfillment status visible for the operations team.",
        }),
      ]),
      createPage("Orders", [responsesSection(form.id), formSection(form.id)]),
    ];

    return createProject({
      name: "Ecommerce Storefront",
      siteChrome: {
        ...defaultSiteChrome,
        brand: "Madar Store",
        footerStoreName: "Madar Store",
        footerShopLinks: "Storefront\nOrders\nLogin",
        description: "A commerce template for product offers, order intake, and fulfillment tracking.",
      },
      pages,
      forms: [form],
      collections: [collection],
      workflows: [createWorkflow("After order is submitted", form.id)],
      roles: common.roles,
      users: common.users,
    });
  }

  if (starterId === "hrFinance") {
    const fields = [
      createField("Employee name", "shortText", { required: true }),
      createField("Department", "dropdown", {
        required: true,
        options: ["HR", "Finance", "Operations", "Programs", "Sales"],
      }),
      createField("Request type", "dropdown", {
        required: true,
        options: ["Leave request", "Reimbursement", "Budget approval", "Payroll support", "Procurement"],
      }),
      createField("Amount", "number", { placeholder: "Example: 7,500" }),
      createField("Due date", "date"),
      createField("Manager approval", "dropdown", {
        options: ["Yes", "No"],
      }),
      createField("Request details", "paragraph", { required: true }),
      createField("Status", "dropdown", {
        options: ["Submitted", "Manager review", "Finance review", "Approved", "Rejected"],
        defaultValue: "Submitted",
      }),
    ];

    const collection = createCollection("HR Finance Requests", fields);
    collection.description = "Employee service requests, approvals, reimbursements, and finance decisions.";

    const form = createForm("Employee Request Form", fields, {
      connectedCollectionId: collection.id,
      description: "Collect HR, finance, payroll, reimbursement, and budget approval requests.",
      successMessage: "Employee request submitted. The review workflow can begin.",
    });

    clearStarterRecords({
      form,
      collection,
    });

    const pages = [
      createPage("Employee Portal", [
        industryHeroSection({
          title: "Run HR and finance requests with clear approval paths",
          description:
            "A staff-service portal for leave, reimbursements, payroll questions, procurement, budgets, and finance review.",
          cta: "Submit employee request",
          formId: form.id,
          imageUrl:
            "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=1400&auto=format&fit=crop",
        }),
        metricsSection(),
        industryCardsSection({
          title: "Built for internal service teams",
          description: "Give employees one clear place to submit requests and give reviewers one place to act.",
          cards: [
            { title: "HR services", description: "Leave, payroll support, employee documentation, and policy requests." },
            { title: "Finance review", description: "Budget approval, reimbursement, procurement, and payment follow-up." },
            { title: "Role-based review", description: "Prepare manager, finance, and admin roles for controlled access." },
          ],
        }),
        industryOperationsSection({
          formId: form.id,
          title: "Approval and request workspace",
          description:
            "Review employee requests, track stage, and keep HR and finance decisions visible.",
        }),
      ]),
      createPage("Review Requests", [responsesSection(form.id), formSection(form.id)]),
    ];

    return createProject({
      name: "HR & Finance Portal",
      siteChrome: {
        ...defaultSiteChrome,
        brand: "Madar HR Finance",
        footerStoreName: "Madar HR Finance",
        footerShopLinks: "Employee Portal\nReview Requests\nLogin",
        description: "A staff portal template for HR services, finance approvals, and internal requests.",
      },
      pages,
      forms: [form],
      collections: [collection],
      workflows: [createWorkflow("After employee request is submitted", form.id)],
      roles: common.roles,
      users: common.users,
    });
  }

  if (starterId === "meal") {
    const fields = [
      createField("Project name", "shortText", { required: true }),
      createField("Location", "shortText"),
      createField("Reporting period", "dropdown", {
        options: ["Weekly", "Monthly", "Quarterly", "Final"],
      }),
      createField("Indicator", "shortText", { required: true }),
      createField("Target value", "number"),
      createField("Actual value", "number"),
      createField("Accountability issue", "paragraph"),
      createField("Learning note", "paragraph"),
      createField("Status", "dropdown", {
        options: ["Draft", "Submitted", "Reviewed", "Action required", "Closed"],
        defaultValue: "Draft",
      }),
    ];

    const collection = createCollection("MEAL Field Reports", fields);
    collection.description = "Project monitoring records with indicators, accountability, and learning notes.";

    const form = createForm("MEAL Field Report Form", fields, {
      connectedCollectionId: collection.id,
      description:
        "Collect monitoring updates, indicator progress, accountability issues, and learning notes from field teams.",
      successMessage: "MEAL report submitted. The coordination team can review and follow up.",
    });

    clearStarterRecords({
      form,
      collection,
    });

    const pages = [
      createPage("MEAL Dashboard", [
        industryHeroSection({
          title: "Coordinate project monitoring, learning, and follow-up",
          description:
            "A MEAL template for project teams managing field reports, indicators, accountability notes, learning logs, and review actions.",
          cta: "Submit field report",
          formId: form.id,
          imageUrl:
            "https://images.unsplash.com/photo-1552664730-d307ca884978?w=1400&auto=format&fit=crop",
        }),
        metricsSection(),
        industryCardsSection({
          title: "For project coordination and MEAL teams",
          description: "Connect field reporting with review, learning, and action tracking.",
          cards: [
            { title: "Indicator tracking", description: "Capture target, actual, location, and reporting period for each update." },
            { title: "Accountability notes", description: "Document feedback, issues, and follow-up needs from communities or partners." },
            { title: "Learning loop", description: "Keep learning notes beside evidence so teams can improve delivery." },
          ],
        }),
        industryOperationsSection({
          formId: form.id,
          title: "Field report review workspace",
          description:
            "Review reports, compare indicator updates, and keep project coordination actions visible.",
        }),
      ]),
      createPage("Field Reports", [responsesSection(form.id), formSection(form.id)]),
    ];

    return createProject({
      name: "MEAL Project Coordination",
      siteChrome: {
        ...defaultSiteChrome,
        brand: "Madar MEAL",
        footerStoreName: "Madar MEAL",
        footerShopLinks: "MEAL Dashboard\nField Reports\nLogin",
        description: "A project coordination template for monitoring, evaluation, accountability, and learning.",
      },
      pages,
      forms: [form],
      collections: [collection],
      workflows: [createWorkflow("After MEAL field report is submitted", form.id)],
      roles: common.roles,
      users: common.users,
    });
  }

  if (starterId === "requests") {
    const collection = createCollection("Requests", [
      createField("Full name", "shortText", { required: true }),
      createField("Request type", "dropdown", {
        required: true,
        options: ["HR", "Finance", "Procurement", "General"],
      }),
      createField("Amount", "number", { placeholder: "Example: 7,500" }),
      createField("Details", "paragraph", { required: true }),
      createField("Status", "dropdown", { options: ["Pending", "Approved", "Rejected"], defaultValue: "Pending" }),
    ]);

    const form = createForm("Request Form", collection.fields, {
      connectedCollectionId: collection.id,
    });

    const pages = [
      createPage("Portal Home", [heroSection(), formSection(form.id)]),
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
      createField("Status", "dropdown", { options: ["Draft", "Submitted", "Reviewed"], defaultValue: "Draft" }),
    ]);

    const form = createForm("Activity Report Form", collection.fields, {
      connectedCollectionId: collection.id,
    });

    const pages = [
      createPage("Monitoring Home", [heroSection(), formSection(form.id)]),
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
      createField("Phone number", "shortText", { required: true, placeholder: "+972 50 123 4567" }),
      createField("Order details", "paragraph", { required: true }),
      createField("Payment amount", "number", { placeholder: "Example: 7,500" }),
      createField("Order status", "dropdown", {
        options: ["New", "Processing", "Ready", "Completed", "Cancelled"],
        defaultValue: "New",
      }),
    ]);

    const form = createForm("Order Form", collection.fields, {
      connectedCollectionId: collection.id,
    });

    const pages = [
      createPage("Store Home", [heroSection(), formSection(form.id)]),
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

  if (starterId === "blankPage") {
    return createProject({
      name: "Blank Page",
      pages: [createPage("Home")],
      roles: common.roles,
      users: common.users,
    });
  }

  const collection = createCollection("Contacts", [
    createField("Full name", "shortText", { required: true }),
    createField("Email", "email", { required: true }),
    createField("Message", "paragraph"),
    createField("Status", "dropdown", { options: ["New", "Contacted", "Closed"], defaultValue: "New" }),
  ]);

  const form = createForm("Contact Form", collection.fields, {
    connectedCollectionId: collection.id,
  });

  return createProject({
    name: "Website + Contact Form",
    siteChrome: {
    ...defaultSiteChrome,
    headerButtonLabel: "Login",
    headerButtonHref: "Login",
    footerShopLinks: "Home\nLogin\nContact",
    },
    pages: [
      createPage("Home", [heroSection(), formSection(form.id)]),
    ],
    forms: [form],
    collections: [collection],
    workflows: [createWorkflow("After contact form is submitted", form.id)],
    roles: common.roles,
    users: common.users,
  });
};

export const createInitialProject = () => buildStarterProject("pilates");

const formatLocalDate = (date) => {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
};

const createPilatesAvailability = () => {
  const offsets = [1, 2, 4, 6, 8];
  const dates = offsets.map((offset) => {
    const date = new Date();
    date.setHours(12, 0, 0, 0);
    date.setDate(date.getDate() + offset);
    return formatLocalDate(date);
  });
  const schedules = [
    ["07:30", "09:00", "17:30"],
    ["08:00", "10:30", "18:30"],
    ["07:30", "12:00", "17:30"],
    ["09:00", "11:00", "18:30"],
    ["08:00", "10:30", "16:30"],
  ];

  return {
    availableDates: dates,
    timeSlots: [...new Set(schedules.flat())],
    timeSlotsByDate: Object.fromEntries(dates.map((date, index) => [date, schedules[index]])),
  };
};

const pilatesHeroSection = (bookingPageId) =>
  createSection({
    name: "Pilates Hero",
    layout: {
      width: "large",
      paddingY: "large",
      background: "var(--theme-bg)",
      minHeight: 620,
    },
    rows: [
      createRow([
        createColumn([
          createElement("text", {
            content: "FORM & FLOW PILATES · SMALL GROUP STUDIO",
            styles: { color: "var(--theme-accent)", fontWeight: "800", letterSpacing: "0.08em" },
          }),
          createElement("heading", {
            content: "Move with strength. Leave with space.",
            styles: { fontSize: "58px", lineHeight: "1.02", color: "var(--theme-text)" },
          }),
          createElement("text", {
            content: "Thoughtful reformer and mat Pilates in a calm, welcoming studio. Small classes, attentive coaching, and movement that meets you where you are.",
          }),
          createElement("button", {
            content: "Book a class",
            action: {
              type: "goToPage",
              pageId: bookingPageId,
            },
            styles: { backgroundColor: "var(--theme-accent)", color: "var(--theme-button-text)" },
          }),
        ]),
        createColumn([
          createElement("image", {
            name: "Pilates Studio",
            content: "https://images.unsplash.com/photo-1518611012118-696072aa579a?w=1400&auto=format&fit=crop",
            styles: { borderRadius: "32px", alignSelf: "stretch" },
          }),
        ]),
      ]),
    ],
  });

const PILATES_CLASSES = [
  { title: "Reformer Foundations", description: "A supportive 50-minute class for learning the equipment and building confident fundamentals.", image: "https://images.unsplash.com/photo-1632077804406-188472f1a810?w=1000&auto=format&fit=crop" },
  { title: "Reformer Flow", description: "A balanced full-body session combining strength, mobility, and smooth transitions.", image: "https://images.unsplash.com/photo-1599901860904-17e6ed7083a0?w=1000&auto=format&fit=crop" },
  { title: "Mat & Mobility", description: "Low-impact core work and restorative mobility with props, breath, and careful pacing.", image: "https://images.unsplash.com/photo-1575052814086-f385e2e2ad1b?w=1000&auto=format&fit=crop" },
];

const pilatesClassesSection = (bookingPageId) =>
  createSection({
    name: "Pilates Classes",
    layout: { width: "large", paddingY: "large", background: "var(--theme-surface)" },
    rows: [
      createRow([
        createColumn([
          createElement("text", {
            content: "CLASSES FOR EVERY BODY",
            styles: { color: "var(--theme-accent)", fontWeight: "800", letterSpacing: "0.08em", textAlign: "center" },
          }),
          createElement("heading", {
            content: "Choose your way to move",
            styles: { fontSize: "42px", textAlign: "center", alignSelf: "stretch" },
          }),
          createElement("text", {
            content: "Every class is built around control, breath, alignment, and progress you can feel.",
            styles: { textAlign: "center", alignSelf: "stretch" },
          }),
        ]),
      ]),
      createRow([
        createColumn([
          createElement("carousel", {
            name: "Pilates Class Gallery",
            content: PILATES_CLASSES.map((item) => (
              `${item.title}\n${item.description}\n${item.image}`
            )).join("\n\n"),
            autoScroll: false,
            styles: {
              backgroundColor: "var(--theme-surface)",
              borderRadius: "24px",
              alignSelf: "stretch",
              "--carousel-height": "460px",
            },
          }),
          createElement("button", {
            content: "View schedule & book",
            action: { type: "goToPage", pageId: bookingPageId },
            styles: { backgroundColor: "var(--theme-accent)", color: "var(--theme-button-text)" },
          }),
        ]),
      ]),
    ],
  });

const createPilatesReservationElement = () => {
  const availability = createPilatesAvailability();
  return createElement("reservationBlock", {
    name: "Pilates Class Booking",
    reservation: {
      title: "Reserve your Reformer class",
      description: "Choose one of the studio's fixed class times, then leave your details. This demo uses sample availability and does not charge a card.",
      services: ["Reformer Pilates"],
      fields: ["name", "email", "phone", "notes"],
      formItems: [],
      bookingMode: "fixed",
      ...availability,
      submitLabel: "Reserve my spot",
    },
    styles: {
      backgroundColor: "var(--theme-surface)",
      borderRadius: "24px",
      alignSelf: "stretch",
    },
  });
};

const pilatesBookingSection = () =>
  createSection({
    name: "Book a Class",
    layout: {
      width: "large",
      paddingY: "large",
      background: "var(--theme-bg-soft)",
      minHeight: 760,
    },
    rows: [
      createRow([
        createColumn([
          createElement("text", {
            content: "YOUR NEXT CLASS",
            styles: { color: "var(--theme-accent)", fontWeight: "800", letterSpacing: "0.08em" },
          }),
          createElement("heading", {
            content: "A simple booking flow with real fixed slots.",
            styles: { fontSize: "42px", lineHeight: "1.08" },
          }),
          createElement("text", {
            content: "Pick a studio date and time, add your contact details, and reserve. Class capacity, schedules, and submissions remain connected to the reservation workspace.",
          }),
          createElement("list", {
            content: "Small groups of up to 8\nBeginner-friendly coaching\nAll equipment included\nArrive 10 minutes early",
          }),
          createElement("image", {
            name: "Reformer class preparation",
            content: "https://images.unsplash.com/photo-1518310383802-640c2de311b2?w=1200&auto=format&fit=crop",
            styles: { borderRadius: "24px", alignSelf: "stretch" },
          }),
        ]),
        createColumn([createPilatesReservationElement()]),
      ]),
    ],
  });

const PILATES_DEMO_PRODUCTS = [
  {
    name: "Studio Grip Socks",
    description: "Soft organic-cotton grip socks for stable reformer sessions.",
    price: "$18",
    image: "https://images.unsplash.com/photo-1582966772680-860e372bb558?w=900&auto=format&fit=crop",
  },
  {
    name: "Cork Massage Ball",
    description: "A compact recovery tool for feet, hips, shoulders, and travel days.",
    price: "$14",
    image: "https://images.unsplash.com/photo-1599447292180-45fd84092ef4?w=900&auto=format&fit=crop",
  },
  {
    name: "Everyday Studio Bottle",
    description: "A lightweight insulated bottle for class, commute, and weekends.",
    price: "$28",
    image: "https://images.unsplash.com/photo-1602143407151-7111542de6e8?w=900&auto=format&fit=crop",
  },
  {
    name: "Linen Carry Tote",
    description: "A relaxed studio tote with room for layers, water, and essentials.",
    price: "$32",
    image: "https://images.unsplash.com/photo-1594223274512-ad4803739b7c?w=900&auto=format&fit=crop",
  },
  {
    name: "Recovery Tea Blend",
    description: "A caffeine-free botanical blend for a slower post-class ritual.",
    price: "$16",
    image: "https://images.unsplash.com/photo-1594631252845-29fc4cc8cde9?w=900&auto=format&fit=crop",
  },
  {
    name: "Movement Journal",
    description: "A simple notebook for class notes, goals, and small wins.",
    price: "$20",
    image: "https://images.unsplash.com/photo-1544816155-12df9643f363?w=900&auto=format&fit=crop",
  },
];

const pilatesShopSection = () =>
  createSection({
    name: "Studio Shop",
    layout: {
      width: "large",
      paddingY: "large",
      background: "var(--theme-surface)",
      minHeight: 760,
    },
    rows: [
      createRow([
        createColumn([
          createElement("text", {
            content: "THE STUDIO EDIT",
            styles: { color: "var(--theme-accent)", fontWeight: "800", letterSpacing: "0.08em", textAlign: "center" },
          }),
          createElement("heading", {
            content: "Useful things for movement and recovery",
            styles: { fontSize: "40px", textAlign: "center", alignSelf: "stretch" },
          }),
        ]),
      ]),
      createRow([
        createColumn([
          createElement("carousel", {
            name: "Studio Shop Gallery",
            content: PILATES_DEMO_PRODUCTS.map((product) => (
              `${product.name}\n${product.description} · ${product.price}\n${product.image}`
            )).join("\n\n"),
            autoScroll: false,
            styles: {
              backgroundColor: "var(--theme-surface)",
              borderRadius: "24px",
              alignSelf: "stretch",
              "--carousel-height": "460px",
            },
          }),
        ]),
      ]),
    ],
  });

const buildPilatesDemoProject = () => {
  const common = createBaseRolesAndUsers();
  const bookingPage = createPage("Book a Class", [pilatesBookingSection()]);
  const studioPage = createPage("Studio", [
    pilatesHeroSection(bookingPage.id),
    pilatesClassesSection(bookingPage.id),
  ]);
  const shopPage = createPage("Shop", [pilatesShopSection()]);

  return createProject({
    name: "Form & Flow",
    theme: PILATES_DEMO_THEME,
    siteChrome: {
      ...defaultSiteChrome,
      brand: "Form & Flow",
      footerStoreName: "Form & Flow",
      headerButtonLabel: "Book a class",
      headerButtonHref: "Book a Class",
      headerButtonPageId: bookingPage.id,
      footerShopLinks: "Studio\nBook a Class\nShop",
      footerHelpLinks: "First visit\nClass guide\nStudio etiquette",
      footerSocialLinks: "Instagram\nYouTube\nPinterest",
      footerPaymentMethods: "Visa\nMastercard\nApple Pay",
      description: "Small-group Pilates, thoughtful coaching, and a studio edit for everyday movement.",
      contactEmail: "hello@formandflow.example",
      phone: "+1 555 014 2026",
    },
    pages: [studioPage, bookingPage, shopPage],
    forms: [],
    collections: [],
    workflows: [],
    roles: common.roles,
    users: common.users,
  });
};
