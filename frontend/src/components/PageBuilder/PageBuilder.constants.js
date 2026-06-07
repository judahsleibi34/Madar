export const STORAGE_KEY = "madar_app_builder_frontend_v4";

export const createId = (prefix = "id") => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return `${prefix}_${crypto.randomUUID()}`;
  }

  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
};

export const slugify = (value = "") => {
  const slug = String(value)
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

  return slug || "page";
};

export const viewports = {
  desktop: 1200,
  tablet: 768,
  mobile: 390,
};

export const builderTabs = [
  {
    id: "design",
    label: "Pages",
    helper: "Design screens, sections, layout, and visual elements.",
  },
  {
    id: "forms",
    label: "Forms",
    helper: "Create forms and place them on pages.",
  },
  {
    id: "users",
    label: "Users",
    helper: "Manage mock team members, roles, and permissions.",
  },
  {
    id: "theme",
    label: "Theme",
    helper: "Control global colors, typography, spacing, and radius.",
  },
  {
    id: "publish",
    label: "Publish",
    helper: "Preview, save locally, export JSON, and publish mock status.",
  },
];

export const designPanels = ["Pages", "Sections", "Layers", "Elements"];

export const sectionWidths = [
  { value: "small", label: "Small" },
  { value: "medium", label: "Medium" },
  { value: "large", label: "Large" },
  { value: "full", label: "Full" },
];

export const spacingOptions = [
  { value: "none", label: "None" },
  { value: "small", label: "Small" },
  { value: "medium", label: "Medium" },
  { value: "large", label: "Large" },
];

export const columnOptions = [
  { value: "1", label: "1 column" },
  { value: "2", label: "2 columns" },
  { value: "3", label: "3 columns" },
  { value: "4", label: "4 columns" },
];

export const alignmentOptions = [
  { value: "left", label: "Left" },
  { value: "center", label: "Center" },
  { value: "right", label: "Right" },
];

export const elementTypes = [
  { id: "heading", label: "Heading", group: "Content" },
  { id: "text", label: "Text", group: "Content" },
  { id: "button", label: "Button", group: "Content" },
  { id: "image", label: "Image", group: "Content" },
  { id: "card", label: "Card", group: "Content" },
  { id: "list", label: "List", group: "Content" },
  { id: "divider", label: "Divider", group: "Content" },
  { id: "embed", label: "Embed", group: "Content" },
  { id: "metric", label: "Metric", group: "Dashboard" },
  { id: "formBlock", label: "Form Block", group: "Connected" },
  { id: "responsesTable", label: "Responses Table", group: "Connected" },
];

export const fieldTypes = [
  { id: "shortText", label: "Short answer", group: "Basic", input: "text" },
  { id: "paragraph", label: "Paragraph", group: "Basic", input: "textarea" },
  { id: "email", label: "Email", group: "Contact", input: "email" },
  { id: "phone", label: "Phone number", group: "Contact", input: "tel" },
  { id: "number", label: "Number", group: "Business", input: "number" },
  { id: "money", label: "Money amount", group: "Business", input: "number" },
  { id: "date", label: "Date", group: "Business", input: "date" },
  { id: "dropdown", label: "Dropdown", group: "Choice", input: "select" },
  { id: "radio", label: "Single choice", group: "Choice", input: "radio" },
  { id: "checkboxes", label: "Checkboxes", group: "Choice", input: "checkboxes" },
  { id: "yesNo", label: "Yes / No", group: "Choice", input: "yesNo" },
  { id: "status", label: "Status", group: "Workflow", input: "select" },
  { id: "file", label: "File upload", group: "Advanced", input: "file" },
];

export const workflowStepTypes = [
  { id: "saveResponse", label: "Save response" },
  { id: "setStatus", label: "Set status" },
  { id: "assignRole", label: "Assign to role" },
  { id: "showMessage", label: "Show message" },
  { id: "sendNotification", label: "Mock notification" },
];

export const permissionGroups = [
  {
    title: "Design",
    permissions: [
      { key: "editPages", label: "Edit pages" },
      { key: "editTheme", label: "Edit theme" },
      { key: "useFreeCanvas", label: "Use free canvas" },
    ],
  },
  {
    title: "Data",
    permissions: [
      { key: "editCollections", label: "Edit collections" },
      { key: "viewResponses", label: "View responses" },
      { key: "exportData", label: "Export data" },
    ],
  },
  {
    title: "Operations",
    permissions: [
      { key: "editWorkflows", label: "Edit workflows" },
      { key: "approveResponses", label: "Approve responses" },
      { key: "manageUsers", label: "Manage users" },
      { key: "publish", label: "Publish" },
    ],
  },
];

export const defaultPermissions = {
  editPages: false,
  editTheme: false,
  useFreeCanvas: false,
  editCollections: false,
  viewResponses: false,
  exportData: false,
  editWorkflows: false,
  approveResponses: false,
  manageUsers: false,
  publish: false,
};

export const defaultTheme = {
  mode: "light",
  name: "Madar Light",
  background: "#f5f2ee",
  surface: "#ffffff",
  softSurface: "#fbfaf8",
  text: "#1a2744",
  muted: "#6d7484",
  primary: "#1a2744",
  accent: "var(--theme-primary)",
  accentDark: "var(--theme-primary-hover)",
  border: "rgba(26, 39, 68, 0.12)",
  radius: 18,
  fontFamily: "Inter",
};

export const themePresets = {
  light: {
    mode: "light",
    name: "Madar Light",
    background: "#f5f2ee",
    surface: "#ffffff",
    softSurface: "#fbfaf8",
    text: "#1a2744",
    muted: "#6d7484",
    primary: "#1a2744",
    accent: "var(--theme-primary)",
    accentDark: "var(--theme-primary-hover)",
    border: "rgba(26, 39, 68, 0.12)",
    radius: 18,
    fontFamily: "Inter",
  },

  dark: {
    mode: "dark",
    name: "Madar Dark",
    background: "#0f0d12",
    surface: "#1b1720",
    softSurface: "#241d27",
    text: "#f4f0e8",
    muted: "#98a4b7",
    primary: "#f4f0e8",
    accent: "#8b1e18",
    accentDark: "#b32620",
    border: "rgba(244, 240, 232, 0.12)",
    radius: 18,
    fontFamily: "Inter",
  },
};

export const defaultSiteChrome = {
  showHeader: true,
  showFooter: true,
  brand: "Madar",
  logoUrl: "",
  headerAlign: "center",
  headerButtonLabel: "Contact",
  description:
    "An adaptive business management platform for creating and managing digital systems.",
  contactEmail: "info@madar.com",
  phone: "+972 0599203857",
  footerStoreName: "Madar",
  rights: "All rights reserved.",
  footerShopTitle: "Pages",
  footerShopLinks: "Home\nSubmit Request\nReports",
  footerHelpTitle: "Help",
  footerHelpLinks: "About Us\nPolicies\nContact",
  footerSocialLinks: "Facebook\nLinkedIn\nX\nInstagram",
  footerPaymentMethods: "Visa\nMastercard\nApple Pay\nGoogle Pay",
  footerLanguageLabel: "AR",
  madarLink: "/",
};

export const starterSystems = [
  {
    id: "website",
    title: "Website + Contact Form",
    subtitle: "Website, contact form, responses, and basic roles.",
  },
  {
    id: "requests",
    title: "Request / Approval Portal",
    subtitle: "HR, finance, procurement, and internal approvals.",
  },
  {
    id: "reports",
    title: "Monitoring / Reporting Hub",
    subtitle: "Activity reports, dashboards, and review workflows.",
  },
  {
    id: "orders",
    title: "Orders / Booking System",
    subtitle: "Customer orders, service bookings, and tracking.",
  },
  {
    id: "blank",
    title: "Blank Custom System",
    subtitle: "Start clean with one page, one form, and admin role.",
  },
];
