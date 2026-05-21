export const STORAGE_KEY = "madar_page_builder_v3";

export const createId = (prefix) => {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return `${prefix}_${crypto.randomUUID()}`;
  }

  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
};

export const slugify = (value) => {
  const slug = String(value || "")
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

export const appTabs = [
  { id: "pages", label: "Pages", help: "Design what people see." },
  { id: "forms", label: "Forms", help: "Build forms like Google Forms." },
  { id: "responses", label: "Responses", help: "Review submitted answers." },
  { id: "automations", label: "Automations", help: "Choose what happens after submit." },
  { id: "users", label: "Users", help: "Manage roles and access." },
  { id: "publish", label: "Publish", help: "Save, preview, export, and publish." },
];

export const defaultWebsiteNav = [
  { id: "home", label: "Home", path: "/" },
  { id: "about", label: "About Us", path: "/about" },
  { id: "features", label: "Features", path: "/features" },
  { id: "contact", label: "Contact Us", path: "/contact" },
  { id: "pricing", label: "Plans and Pricing", path: "/pricing" },
];

export const defaultSiteChrome = {
  brand: "Madar",
  description:
    "An adaptive business management platform for creating and managing digital systems.",
  contactEmail: "info@madar.com",
  phone: "+972 0599203857",
  rights: "All rights reserved.",
};

export const pagePanels = ["Pages", "Sections", "Layers", "Add"];

export const friendlyQuestionTypes = [
  {
    id: "shortText",
    label: "Short answer",
    group: "Basic",
    placeholder: "Short answer text",
  },
  {
    id: "paragraph",
    label: "Paragraph",
    group: "Basic",
    placeholder: "Long answer text",
  },
  {
    id: "number",
    label: "Number",
    group: "Basic",
    placeholder: "123",
  },
  {
    id: "date",
    label: "Date",
    group: "Basic",
    placeholder: "Select date",
  },
  {
    id: "email",
    label: "Email",
    group: "Contact",
    placeholder: "name@example.com",
  },
  {
    id: "phone",
    label: "Phone number",
    group: "Contact",
    placeholder: "+962...",
  },
  {
    id: "money",
    label: "Money amount",
    group: "Business",
    placeholder: "0.00",
  },
  {
    id: "dropdown",
    label: "Dropdown",
    group: "Choices",
    placeholder: "Choose one",
  },
  {
    id: "multipleChoice",
    label: "Multiple choice",
    group: "Choices",
    placeholder: "Choose one",
  },
  {
    id: "checkboxes",
    label: "Checkboxes",
    group: "Choices",
    placeholder: "Choose one or more",
  },
  {
    id: "yesNo",
    label: "Yes / No",
    group: "Choices",
    placeholder: "Yes or No",
  },
  {
    id: "file",
    label: "File upload",
    group: "Business",
    placeholder: "Upload file",
  },
  {
    id: "status",
    label: "Progress status",
    group: "Business",
    placeholder: "Pending",
  },
];

export const elementTypes = [
  { id: "heading", label: "Heading", group: "Content" },
  { id: "text", label: "Text", group: "Content" },
  { id: "button", label: "Button", group: "Content" },
  { id: "image", label: "Image", group: "Content" },
  { id: "card", label: "Card", group: "Content" },
  { id: "formBlock", label: "Form Block", group: "Connected" },
  { id: "responsesTable", label: "Responses Table", group: "Connected" },
  { id: "metric", label: "Metric", group: "Connected" },
];

export const starterSystems = [
  {
    id: "website",
    title: "Website + Contact Form",
    subtitle: "Best for organizations, portfolios, services, and simple websites.",
    creates: ["Home page", "Contact form", "Responses table", "Basic roles"],
  },
  {
    id: "requests",
    title: "Request / Approval Portal",
    subtitle: "Best for HR, finance, procurement, support, or applications.",
    creates: ["Request form", "Approval responses", "Status tracking", "Reviewer role"],
  },
  {
    id: "reports",
    title: "Monitoring / Reporting Hub",
    subtitle: "Best for MEAL, project coordinators, field reports, and activity logs.",
    creates: ["Report form", "Reports table", "Dashboard metrics", "Coordinator role"],
  },
  {
    id: "orders",
    title: "Orders / Booking System",
    subtitle: "Best for restaurants, product orders, services, bookings, and requests.",
    creates: ["Order form", "Customer responses", "Status tracking", "Staff role"],
  },
  {
    id: "blank",
    title: "Blank Custom System",
    subtitle: "Start clean and build your own pages, forms, responses, and automations.",
    creates: ["Home page", "Blank form", "Admin role"],
  },
];