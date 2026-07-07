const authSessionMessages = {
  "auth.session.access_expired": "Your session expired. Please log in again.",
  "auth.session.invalid": "Your session is invalid or expired. Please log in again.",
};

export const normalizeAuthMessage = (detail, fallback) => {
  if (typeof detail !== "string") return fallback;
  return authSessionMessages[detail] || detail || fallback;
};

export const formatAuthValidationToastMessage = (errors, labels) => {
  const fields = Object.keys(errors || {})
    .filter((key) => Boolean(errors[key]))
    .map((key) => labels[key] || key);

  if (fields.length === 0) return "";

  const messages = Object.keys(errors || {})
    .filter((key) => Boolean(errors[key]))
    .map((key) => String(errors[key]).toLowerCase());
  const allRequired = messages.every((message) => message.includes("required"));

  if (allRequired) {
    if (fields.length === 1) return `${fields[0]} is required.`;
    if (fields.length === 2) return `${fields[0]} and ${fields[1]} are required.`;
    return `${fields.slice(0, -1).join(", ")}, and ${fields[fields.length - 1]} are required.`;
  }

  if (fields.length === 1) return `${fields[0]} needs attention.`;
  if (fields.length === 2) return `${fields[0]} and ${fields[1]} need attention.`;

  return `${fields.slice(0, -1).join(", ")}, and ${fields[fields.length - 1]} need attention.`;
};
