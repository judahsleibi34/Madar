const isEmpty = (value) =>
  value === undefined ||
  value === null ||
  (typeof value === "string" && value.trim() === "") ||
  (Array.isArray(value) && value.length === 0);

const unwrapValue = (value) =>
  value && typeof value === "object" && !Array.isArray(value) && "value" in value
    ? value.value
    : value;

const validCalendarDate = (value) => {
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) return false;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return date.getUTCFullYear() === Number(match[1]) &&
    date.getUTCMonth() === Number(match[2]) - 1 &&
    date.getUTCDate() === Number(match[3]);
};

const optionValue = (value) => String(unwrapValue(value) ?? "");

const availableOptions = (field) => (Array.isArray(field?.options) ? field.options : [])
  .map((option) => optionValue(option))
  .filter(Boolean);

export const getRuntimeFieldError = (field = {}, rawValue) => {
  const value = unwrapValue(rawValue);
  const label = String(field.label || "This field").trim() || "This field";

  if (isEmpty(value)) {
    return field.required ? `${label} is required.` : "";
  }

  const text = String(value).trim();
  switch (field.type) {
    case "email":
      return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(text) ? "" : "Enter a valid email address.";
    case "url":
    case "website": {
      try {
        const url = new URL(text);
        return ["http:", "https:"].includes(url.protocol) ? "" : "Enter a valid website address.";
      } catch {
        return "Enter a valid website address.";
      }
    }
    case "phone": {
      const digits = text.replace(/\D/g, "");
      return /^[+()\d\s.-]+$/.test(text) && digits.length >= 7 && digits.length <= 15
        ? ""
        : "Enter a valid phone number.";
    }
    case "number":
      return Number.isFinite(Number(text)) ? "" : "Enter a valid number.";
    case "money":
      return Number.isFinite(Number(text.replace(/,/g, ""))) ? "" : "Enter a valid amount.";
    case "date":
      return validCalendarDate(text) ? "" : "Choose a valid date.";
    case "time":
      return /^([01]\d|2[0-3]):[0-5]\d$/.test(text) ? "" : "Choose a valid time.";
    case "dropdown":
    case "status":
    case "radio": {
      const options = availableOptions(field);
      return options.length === 0 || options.includes(optionValue(rawValue))
        ? ""
        : "Choose one of the available options.";
    }
    case "checkboxes": {
      if (!Array.isArray(rawValue)) return "Choose only from the available options.";
      const options = availableOptions(field);
      return options.length === 0 || rawValue.every((item) => options.includes(optionValue(item)))
        ? ""
        : "Choose only from the available options.";
    }
    case "linearScale":
    case "rating": {
      const number = Number(value);
      const min = field.type === "rating" ? 1 : Number(field.scaleMin || 1);
      const max = field.type === "rating" ? Number(field.maxRating || 5) : Number(field.scaleMax || 5);
      return Number.isInteger(number) && number >= min && number <= max
        ? ""
        : `Choose a value from ${min} to ${max}.`;
    }
    case "file": {
      if (!rawValue || typeof rawValue !== "object" || Array.isArray(rawValue) || !String(rawValue.name || "").trim()) {
        return "Choose a valid file.";
      }
      const maxBytes = Number(field.maxFileSizeMb || 0) * 1024 * 1024;
      return maxBytes > 0 && Number(rawValue.size || 0) > maxBytes
        ? `Choose a file smaller than ${field.maxFileSizeMb}MB.`
        : "";
    }
    default:
      return typeof value === "object" ? `${label} contains an invalid value.` : "";
  }
};

export const getRuntimeFormErrors = (fields = [], answers = {}) =>
  fields.reduce((errors, field) => {
    const error = getRuntimeFieldError(field, answers[field.id]);
    if (error) errors[field.id] = error;
    return errors;
  }, {});

