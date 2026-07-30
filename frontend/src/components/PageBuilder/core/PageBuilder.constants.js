export const STORAGE_KEY = "madar_app_builder_frontend_v4";

export const getBuilderStorageKey = (userId) => {
  const normalizedUserId = String(userId ?? "").trim();
  return normalizedUserId ? `${STORAGE_KEY}:user:${normalizedUserId}` : `${STORAGE_KEY}:anonymous`;
};

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
    id: "reservations",
    label: "Reservations",
    helper: "Edit appointment blocks, services, and time slots.",
  },
  {
    id: "chrome",
    label: "Header & Footer",
    helper: "Manage the site header, footer, navigation, links, and contact details.",
  },
  {
    id: "users",
    label: "Users",
    helper: "Manage team members, roles, and permissions.",
  },
  {
    id: "theme",
    label: "Themes",
    helper: "Control builder canvas colors, typography, buttons, and theme styling.",
  },
  {
    id: "publish",
    label: "Publish",
    helper: "Preview, save locally, export JSON, and publish mock status.",
  },
];

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
  { id: "reservationRequest", label: "Date request", group: "Bookings" },
  { id: "reservationFixedSlots", label: "Fixed slots", group: "Bookings" },
  { id: "heading", label: "Heading", group: "Content" },
  { id: "text", label: "Text", group: "Content" },
  { id: "button", label: "Button", group: "Content" },
  { id: "image", label: "Image", group: "Content" },
  { id: "photoProofing", label: "Photo Proofing", group: "Media" },
  { id: "card", label: "Card", group: "Content" },
  { id: "carousel", label: "Card Carousel", group: "Content" },
  { id: "list", label: "List", group: "Content" },
  { id: "divider", label: "Divider", group: "Content" },
  { id: "thinDivider", label: "Horizontal Line", group: "Content" },
  { id: "embed", label: "Embed", group: "Content" },
  { id: "metric", label: "Metric", group: "Dashboard" },
  { id: "loginBlock", label: "Login Form", group: "Auth" },
  { id: "registrationBlock", label: "Registration Form", group: "Auth" },
  { id: "formBlock", label: "Form Block", group: "Connected" },
];

export const fieldTypes = [
  { id: "shortText", label: "Short answer", group: "Text", input: "text" },
  { id: "paragraph", label: "Long answer", group: "Text", input: "textarea" },
  { id: "email", label: "Email", group: "Contact", input: "email" },
  { id: "number", label: "Numeric answer", group: "Number", input: "number" },
  { id: "date", label: "Date", group: "Date", input: "date" },
  { id: "dropdown", label: "Dropdown menu", group: "Choice", input: "select" },
  { id: "radio", label: "Radio buttons", group: "Choice", input: "radio" },
  { id: "checkboxes", label: "Checkboxes", group: "Choice", input: "checkboxes" },
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
    title: "Site access",
    permissions: [
      { key: "viewProtectedPages", label: "View allowed protected pages" },
      { key: "submitForms", label: "Submit allowed forms" },
      { key: "makeReservations", label: "Book allowed reservations" },

    ],
  },
];

export const defaultPermissions = {
  viewProtectedPages: false,
  submitForms: false,
  makeReservations: false,

};
export const defaultTheme = {
  mode: "light",
  name: "Madar Light",
  background: "#f4f0e8",
  surface: "#fffdfa",
  softSurface: "#f8f4ed",
  text: "#162033",
  muted: "#6f7787",
  primary: "#162033",
  accent: "#852c21",
  accentDark: "#6f241b",
  buttonText: "#ffffff",
  border: "rgba(27, 42, 74, 0.12)",
  radius: 18,
  fontFamily: "Inter",
};

export const themePresets = {
  light: {
    mode: "light",
    name: "Madar Light",
    background: "#f4f0e8",
    surface: "#fffdfa",
    softSurface: "#f8f4ed",
    text: "#162033",
    muted: "#6f7787",
    primary: "#162033",
    accent: "#852c21",
    accentDark: "#6f241b",
    buttonText: "#ffffff",
    border: "rgba(27, 42, 74, 0.12)",
    radius: 18,
    fontFamily: "Inter",
  },

  dark: {
    mode: "dark",
    name: "Madar Dark",
    background: "#101317",
    surface: "#181d23",
    softSurface: "#232a32",
    text: "#f4f6f8",
    muted: "#9ca6b2",
    primary: "#f4f6f8",
    accent: "#852c21",
    accentDark: "#c94730",
    buttonText: "#ffffff",
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
  loadingImageUrl: "",
  headerAlign: "center",
  headerButtonLabel: "Contact",
  headerButtonHref: "Contact",
  headerButtonPageId: "",
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
  footerSocialItems: [],
  footerPaymentMethods: "Visa\nMastercard\nApple Pay\nGoogle Pay",
  footerPaymentItems: [],
  footerLanguageLabel: "AR",
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
  {
    id: "blankPage",
    title: "Blank Page",
    subtitle: "Start with one completely empty page.",
  },
];
