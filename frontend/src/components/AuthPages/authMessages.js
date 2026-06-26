const authSessionMessages = {
  "auth.session.access_expired": "Your session expired. Please log in again.",
  "auth.session.invalid": "Your session is invalid or expired. Please log in again.",
};

export const normalizeAuthMessage = (detail, fallback) => {
  if (typeof detail !== "string") return fallback;
  return authSessionMessages[detail] || detail || fallback;
};
