export const getModernFieldPlaceholder = (field = {}) => {
  const customPlaceholder = String(field.placeholder || "").trim();
  const genericPlaceholders = new Set([
    "",
    "Short answer",
    "Short text",
    "Paragraph",
    "Long text",
    "Email",
    "Email address",
    "Phone number",
    "Website URL",
    "Number",
    "Money amount",
    "Price or budget",
    "Date",
    "Date picker",
    "Time",
    "Dropdown",
    "Dropdown menu",
    "Single choice",
    "Radio buttons",
    "Checkboxes",
    "Checkbox list",
    "Yes / No",
    "Yes or no",
    "Linear scale",
    "Rating",
    "Status",
    "Status selector",
    "File upload",
  ]);

  if (!genericPlaceholders.has(customPlaceholder)) return customPlaceholder;

  const label = String(field.label || "").toLowerCase();

  if (field.type === "email" || label.includes("email")) return "name@company.com";
  if (field.type === "phone" || label.includes("phone")) return "+972 50 123 4567";
  if (field.type === "url" || label.includes("website")) return "https://yourcompany.com";
  if (field.type === "money" || label.includes("budget") || label.includes("amount")) return "Example: 7,500";
  if (field.type === "number" || label.includes("size")) return "Example: 12";
  if (field.type === "date") return "Select a date";
  if (field.type === "time") return "Select a time";
  if (field.type === "dropdown" || field.type === "status") return "Select an option";
  if (field.type === "radio") return "Choose one option";
  if (field.type === "checkboxes") return "Select all that apply";

  if (field.type === "paragraph" || label.includes("summary") || label.includes("details")) {
    return "Briefly describe what you need...";
  }

  if (label.includes("name")) return "e.g. Sarah Haddad";

  return "Type your answer";
};

export const getFieldOptions = (field) => (field.options || []).filter(Boolean);

export const scaleRange = (field) => {
  const min = Number(field.scaleMin || 1);
  const max = Math.max(min, Number(field.scaleMax || 5));

  return Array.from({ length: max - min + 1 }, (_, index) => String(min + index));
};
