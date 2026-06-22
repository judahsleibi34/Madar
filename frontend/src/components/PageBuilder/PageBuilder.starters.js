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
      width: "full",
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

export const showcaseHeroSection = (formId = "") =>
  createSection({
    name: "Showcase Hero",
    layout: {
      width: "large",
      paddingY: "large",
      background: "#fbfaf8",
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
      background: "#ffffff",
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
    name: "Carousel Gallery",
    layout: {
      width: "large",
      paddingY: "large",
      background: "#fbfaf8",
      minHeight: 980,
    },
    rows: [
      createRow([
        createColumn([
          createElement("heading", {
            content: "Carousel variants",
            styles: { fontSize: "38px", textAlign: "center", alignSelf: "stretch" },
          }),
          createElement("text", {
            content:
              "Show offers, stories, featured services, galleries, and product collections with different carousel layouts.",
            styles: { textAlign: "center", alignSelf: "stretch" },
          }),
        ]),
      ]),
      createRow([
        createColumn([createElement("carousel")]),
        createColumn([createElement("carouselCards")]),
      ]),
      createRow([
        createColumn([createElement("carouselSplit")]),
        createColumn([createElement("circularGallery")]),
      ]),
    ],
  });

export const showcaseConnectedSection = (formId = "") =>
  createSection({
    name: "Connected Operations",
    layout: {
      width: "large",
      paddingY: "large",
      background: "#ffffff",
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
      background: "#fbfaf8",
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

export const sectionLibrary = [
  { id: "hero", title: "Hero Section", category: "Website", description: "Headline, text, button, and card.", create: heroSection },
  { id: "login", title: "Login Section", category: "Auth", description: "Login page block for private/internal website areas.", create: loginSection },
  { id: "form", title: "Form Section", category: "Forms", description: "Place the active form on the page.", create: formSection },
  { id: "metrics", title: "Metrics Section", category: "Dashboard", description: "Counters for responses and statuses.", create: metricsSection },
];

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
  cta = "Submit request",
  imageUrl,
  formId = "",
}) =>
  createSection({
    name: "Hero",
    layout: {
      width: "large",
      paddingY: "large",
      background: "#fbfaf8",
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
      background: "#ffffff",
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
      background: "#fbfaf8",
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
            content: "Open items\n24",
          }),
          createElement("metric", {
            content: "Ready for review\n8",
          }),
        ]),
      ]),
    ],
  });

const addSampleResponse = ({ form, collection, fields, answers, status = "New" }) => {
  const response = {
    id: `response_${collection.key}_sample`,
    createdAt: "2026-05-25T08:00:00.000Z",
    status,
    answers: fields.reduce((acc, field, index) => {
      acc[field.id] = answers[index] ?? "";
      return acc;
    }, {}),
  };

  form.responses = [response];
  collection.records = [response];
};

export const buildStarterProject = (starterId = "website") => {
  const common = createBaseRolesAndUsers();

  if (starterId === "showcase") {
    const fields = [
      createField("Full name", "shortText", { required: true }),
      createField("Email", "email", { required: true }),
      createField("Phone number", "phone"),
      createField("Company website", "url"),
      createField("Request summary", "paragraph", { required: true }),
      createField("Department", "dropdown", {
        required: true,
        options: ["Sales", "Operations", "Finance", "Support"],
      }),
      createField("Priority", "radio", {
        options: ["Low", "Medium", "High"],
        defaultValue: "Medium",
      }),
      createField("Needed services", "checkboxes", {
        options: ["Website", "Forms", "Reports", "Automation"],
      }),
      createField("Approved to contact", "yesNo"),
      createField("Expected budget", "money"),
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
      createField("Status", "status", {
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

    const sampleResponse = {
      id: "response_showcase_sample",
      createdAt: "2026-05-25T08:00:00.000Z",
      status: "New",
      answers: {
        [fields[0].id]: "Sample Customer",
        [fields[1].id]: "customer@example.com",
        [fields[2].id]: "+972599203857",
        [fields[3].id]: "https://madar.com",
        [fields[4].id]: "Launch a service portal with intake, booking, reporting, and approvals.",
        [fields[5].id]: "Operations",
        [fields[6].id]: "High",
        [fields[7].id]: ["Website", "Forms", "Reports"],
        [fields[8].id]: "Yes",
        [fields[9].id]: "7500",
        [fields[10].id]: "12",
        [fields[11].id]: "2026-06-10",
        [fields[12].id]: "10:30",
        [fields[13].id]: "9",
        [fields[14].id]: "5",
        [fields[15].id]: "brief.pdf",
        [fields[16].id]: "New",
      },
    };

    form.responses = [sampleResponse];
    collection.records = [sampleResponse];

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
      createField("Status", "status", {
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

    addSampleResponse({
      form,
      collection,
      fields,
      status: "In review",
      answers: [
        "Customer onboarding guide",
        "Resource",
        "Content Manager",
        "2026-06-12",
        "Customers",
        "Create a practical onboarding guide with setup steps, support links, and common questions.",
        "In review",
      ],
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
      createField("Phone number", "phone", { required: true }),
      createField("Product or service", "dropdown", {
        required: true,
        options: ["Starter package", "Growth package", "Custom order", "Consultation"],
      }),
      createField("Quantity", "number"),
      createField("Delivery date", "date"),
      createField("Order notes", "paragraph"),
      createField("Order status", "status", {
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

    addSampleResponse({
      form,
      collection,
      fields,
      status: "Confirmed",
      answers: [
        "Maya Haddad",
        "maya@example.com",
        "+972 50 555 1212",
        "Growth package",
        "2",
        "2026-06-18",
        "Need delivery before the weekend.",
        "Confirmed",
      ],
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
      createField("Amount", "money"),
      createField("Due date", "date"),
      createField("Manager approval", "yesNo"),
      createField("Request details", "paragraph", { required: true }),
      createField("Status", "status", {
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

    addSampleResponse({
      form,
      collection,
      fields,
      status: "Finance review",
      answers: [
        "Omar Salim",
        "Programs",
        "Reimbursement",
        "420",
        "2026-06-08",
        "Yes",
        "Travel reimbursement for project coordination meetings.",
        "Finance review",
      ],
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
      createField("Status", "status", {
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

    addSampleResponse({
      form,
      collection,
      fields,
      status: "Reviewed",
      answers: [
        "Youth employment program",
        "North district",
        "Monthly",
        "Participants completing training",
        "120",
        "108",
        "Two partner sites requested clearer feedback channels.",
        "Evening sessions improved attendance for working participants.",
        "Reviewed",
      ],
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
      createField("Amount", "money"),
      createField("Details", "paragraph", { required: true }),
      createField("Status", "status", { options: ["Pending", "Approved", "Rejected"], defaultValue: "Pending" }),
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
      createField("Status", "status", { options: ["Draft", "Submitted", "Reviewed"], defaultValue: "Draft" }),
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

export const createInitialProject = () => buildStarterProject("showcase");
