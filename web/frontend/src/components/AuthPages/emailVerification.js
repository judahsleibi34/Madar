const PENDING_EMAIL_STORAGE_KEY = "madar.pending-verification-email";

export const normalizePendingEmail = (value) =>
  String(value || "").trim().toLowerCase();

export const maskEmail = (value) => {
  const email = normalizePendingEmail(value);
  const atIndex = email.lastIndexOf("@");

  if (atIndex <= 0 || atIndex === email.length - 1) return "your email address";

  const local = email.slice(0, atIndex);
  const domain = email.slice(atIndex + 1);
  const domainParts = domain.split(".");
  const domainName = domainParts.shift() || "";
  const suffix = domainParts.length > 0 ? `.${domainParts.join(".")}` : "";
  const maskedLocal = `${local.slice(0, 1)}${"*".repeat(Math.min(3, Math.max(1, local.length - 1)))}`;
  const maskedDomain = `${domainName.slice(0, 1)}${"*".repeat(Math.min(3, Math.max(1, domainName.length - 1)))}`;

  return `${maskedLocal}@${maskedDomain}${suffix}`;
};

const getSessionStorage = () => {
  try {
    return typeof window === "undefined" ? null : window.sessionStorage;
  } catch {
    return null;
  }
};

export const rememberPendingVerificationEmail = (value) => {
  const email = normalizePendingEmail(value);
  const storage = getSessionStorage();

  if (!email) {
    storage?.removeItem(PENDING_EMAIL_STORAGE_KEY);
    return "";
  }

  storage?.setItem(PENDING_EMAIL_STORAGE_KEY, email);
  return email;
};

export const readPendingVerificationEmail = () =>
  normalizePendingEmail(getSessionStorage()?.getItem(PENDING_EMAIL_STORAGE_KEY));

export const clearPendingVerificationEmail = () => {
  getSessionStorage()?.removeItem(PENDING_EMAIL_STORAGE_KEY);
};

export const readVerificationCallback = (locationLike = {}) => {
  const hashParams = new URLSearchParams(String(locationLike.hash || "").replace(/^#/, ""));
  const queryParams = new URLSearchParams(String(locationLike.search || "").replace(/^\?/, ""));
  const errorCode = hashParams.get("error_code") || queryParams.get("error_code") || "";
  const error = hashParams.get("error") || queryParams.get("error") || "";
  const description =
    hashParams.get("error_description") || queryParams.get("error_description") || "";

  return {
    accessToken: hashParams.get("access_token") || "",
    callbackType: hashParams.get("type") || queryParams.get("type") || "",
    exchangeCode: queryParams.get("code") || "",
    error,
    errorCode,
    description,
    hasProviderError: Boolean(error || errorCode),
  };
};

export const clearVerificationCallbackFromAddressBar = (locationLike = {}) => {
  if (typeof window === "undefined" || !window.history?.replaceState) return;

  const searchParams = new URLSearchParams(
    String(locationLike.search || window.location.search || "").replace(/^\?/, "")
  );
  ["code", "error", "error_code", "error_description", "type", "verified"].forEach(
    (key) => searchParams.delete(key)
  );
  const cleanQuery = searchParams.toString();
  const cleanPath = `${locationLike.pathname || window.location.pathname}${cleanQuery ? `?${cleanQuery}` : ""}`;
  window.history.replaceState(window.history.state, document.title, cleanPath);
};

export const getVerificationErrorState = ({ error = "", errorCode = "", description = "" } = {}) => {
  const value = `${error} ${errorCode} ${description}`.toLowerCase();

  if (/expired|otp_expired/.test(value)) return "expired";
  if (value.trim()) return "invalid";
  return "";
};

export const isEmailVerificationRequiredError = (data) => {
  const detail = data?.detail;
  const code = data?.code || detail?.code || data?.error?.code || "";
  const message =
    typeof detail === "string"
      ? detail
      : typeof detail?.message === "string"
        ? detail.message
        : "";

  return (
    code === "email_verification_required" ||
    message.toLowerCase().includes("verify your email")
  );
};
