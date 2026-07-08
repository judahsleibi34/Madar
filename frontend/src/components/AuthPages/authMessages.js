const authSessionMessages = {
  "auth.session.access_expired": "Your session expired. Please log in again.",
  "auth.session.invalid": "Your session is invalid or expired. Please log in again.",
};

const userSafeAuthMessages = new Set([
  "account created. please verify your email before logging in.",
  "could not create account",
  "could not create user",
  "could not start mfa challenge",
  "could not verify mfa code",
  "email is already registered",
  "invalid email or password",
  "invalid or expired reset link.",
  "mfa login session expired",
  "password must be at least 8 characters",
  "please verify your email before logging in.",
]);

const technicalErrorPatterns = [
  /\b\d{3}\b/,
  /\bapierror\b/,
  /\bbad gateway\b/,
  /\bconnection\b/,
  /\bdatabase\b/,
  /\bexception\b/,
  /\bfailed to fetch\b/,
  /\bgateway\b/,
  /\binternal server error\b/,
  /\bnetwork\b/,
  /\bproxy\b/,
  /\bservice unavailable\b/,
  /\btimeout\b/,
  /\btraceback\b/,
  /\bupstream\b/,
];

export const normalizeAuthMessage = (detail, fallback) => {
  if (typeof detail !== "string") return fallback;

  const message = detail.trim();
  if (!message) return fallback;

  if (authSessionMessages[message]) return authSessionMessages[message];

  const normalizedMessage = message.toLowerCase();
  if (userSafeAuthMessages.has(normalizedMessage)) return message;
  if (technicalErrorPatterns.some((pattern) => pattern.test(normalizedMessage))) return fallback;

  return fallback;
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
