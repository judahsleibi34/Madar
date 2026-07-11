const builderWorkspaceCopyEn = {
  projectNames: {
    "Madar Builder Demo": "Madar Builder Demo",
  },
  topbar: {
    templates: "Templates",
    preview: "Preview site",
    exitPreview: "Exit site preview",
    save: "Save builder",
    goLive: "Go Live",
    publishing: "Publishing...",
  },
  tabs: {
    design: {
      label: "Pages",
      helper: "Design screens, sections, layout, and visual elements.",
    },
    forms: {
      label: "Forms",
      helper: "Create forms and place them on pages.",
    },
    reservations: {
      label: "Reservations",
      helper: "Edit appointment blocks, services, and time slots.",
    },
    chrome: {
      label: "Header & Footer",
      helper: "Manage the site header, footer, navigation, links, and contact details.",
    },
    users: {
      label: "Users",
      helper: "Manage team members, roles, and permissions.",
    },
    theme: {
      label: "Themes",
      helper: "Control builder canvas colors, typography, buttons, and theme styling.",
    },
    publish: {
      label: "Publish",
      helper: "Preview, save, export, and publish the builder site.",
    },
    responses: {
      label: "Responses",
      helper: "Review submitted form answers.",
    },
    data: {
      label: "Data",
      helper: "Review, clean, and analyze your collected data.",
    },
  },
};

const mobileBlockerCopyEn = {
  design: {
    title: "Desktop builder only",
    message:
      "The page builder is designed for tablet and desktop editing. Use a wider screen to build layouts, forms, workflows, and themes comfortably.",
  },
  data: {
    title: "Data workspace needs more room",
    message:
      "Data review, cleaning, and reporting are designed for tablet and desktop screens. Use a wider screen to inspect tables and generate reports comfortably.",
  },
  responses: {
    title: "Submissions are easier on a wider screen",
    message:
      "Response review is designed for tablet and desktop screens. Use a wider screen to scan submissions, compare answers, and export data comfortably.",
  },
  default: {
    title: "Desktop workspace only",
    message:
      "This workspace is designed for tablet and desktop screens. Use a wider screen for the best editing experience.",
  },
};

const templateModalTextEn = {
  eyebrow: "Template library",
  title: "Choose a builder template",
  description:
    "Start from a focused operating system, then edit pages, forms, data, roles, workflows, and theme values.",
  close: "Close",
};

const starterTextEn = {
  showcase: {
    category: "Demo",
    title: "Full Builder Showcase",
    subtitle:
      "Complete default template showing pages, forms, data, media, login, and workflows.",
    tags: ["All features", "Demo"],
  },
  cms: {
    category: "Content management",
    title: "CMS Content Hub",
    subtitle:
      "Editorial pages, intake forms, publishing workflow, content records, and team roles.",
    tags: ["Content", "Publishing", "Approvals"],
  },
  ecommerce: {
    category: "Commerce",
    title: "Ecommerce Storefront",
    subtitle:
      "Product display, order intake, customer records, fulfillment status, and booking-ready operations.",
    tags: ["Products", "Orders", "Customers"],
  },
  hrFinance: {
    category: "Operations",
    title: "HR & Finance Portal",
    subtitle:
      "Employee requests, budget approvals, reimbursements, payroll support, and role-based review.",
    tags: ["HR", "Finance", "Approvals"],
  },
  meal: {
    category: "Projects",
    title: "MEAL Project Coordination",
    subtitle:
      "Monitoring, evaluation, accountability, learning, field reports, indicators, and partner follow-up.",
    tags: ["MEAL", "Projects", "Reports"],
  },
  blankPage: {
    title: "Blank page",
    subtitle: "Start with one completely blank page.",
  },
  website: {
    title: "Website and contact form",
    subtitle: "Website, contact form, responses, and basic roles.",
  },
  requests: {
    title: "Requests and approvals portal",
    subtitle: "HR, finance, procurement, and internal approval requests.",
  },
  reports: {
    title: "Monitoring and reporting hub",
    subtitle: "Activity reports, dashboards, and review workflow.",
  },
  orders: {
    title: "Orders and booking system",
    subtitle: "Customer orders, service bookings, and status tracking.",
  },
  blank: {
    title: "Blank custom system",
    subtitle: "Start with one page, one form, and one admin role.",
  },
};

export const mainBuilderHiddenTabs = ["data", "responses", "theme"];

export const pageBuilderContent = {
  en: {
    builderWorkspaceCopy: builderWorkspaceCopyEn,
    mobileBlockerCopy: mobileBlockerCopyEn,
    templateModalText: templateModalTextEn,
    starterText: starterTextEn,
  },
  ar: {
    builderWorkspaceCopy: builderWorkspaceCopyEn,
    mobileBlockerCopy: mobileBlockerCopyEn,
    templateModalText: templateModalTextEn,
    starterText: starterTextEn,
  },
};

export function getPageBuilderContent(lang = "en") {
  return pageBuilderContent[lang] || pageBuilderContent.en;
}

export const builderWorkspaceCopy = {
  en: pageBuilderContent.en.builderWorkspaceCopy,
  ar: pageBuilderContent.ar.builderWorkspaceCopy,
};

export const mobileBlockerCopy = {
  en: pageBuilderContent.en.mobileBlockerCopy,
  ar: pageBuilderContent.ar.mobileBlockerCopy,
};

export const templateModalText = {
  en: pageBuilderContent.en.templateModalText,
  ar: pageBuilderContent.ar.templateModalText,
};

export const starterArabicText = pageBuilderContent.ar.starterText;

export const internalPageNames = new Set([
  "review responses",
  "responses",
  "reports",
  "orders",
  "submit request",
  "submit report",
  "place order",
]);
