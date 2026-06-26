export const CSRF_HEADER_NAME = "X-CSRF-Token";
export const CSRF_COOKIE_NAME = "madar_csrf_token";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

let csrfToken = "";

const getCookieValue = (name) => {
  if (typeof document === "undefined") return "";

  return (
    document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(`${name}=`))
      ?.slice(name.length + 1) || ""
  );
};

export const getCsrfToken = () => csrfToken || decodeURIComponent(getCookieValue(CSRF_COOKIE_NAME));

export const setCsrfToken = (token) => {
  csrfToken = token || getCsrfToken() || "";
  return csrfToken;
};

export const clearCsrfToken = () => {
  csrfToken = "";
};

export const syncCsrfTokenFromResponseData = (data) => {
  if (data?.csrf_token) {
    setCsrfToken(data.csrf_token);
  }
};

export const apiFetch = async (input, init = {}) => {
  const method = String(init.method || "GET").toUpperCase();
  const headers = new Headers(init.headers || {});

  if (UNSAFE_METHODS.has(method) && !headers.has(CSRF_HEADER_NAME)) {
    const token = getCsrfToken();

    if (token) {
      headers.set(CSRF_HEADER_NAME, token);
    }
  }

  const runFetch = () => fetch(input, {
    ...init,
    method,
    credentials: init.credentials || "include",
    headers,
  });

  const inputUrl = typeof input === "string" ? input : input?.url || "";
  const serializesAuthSession =
    (method === "GET" && inputUrl.includes("/auth/user_status")) ||
    (method === "POST" && inputUrl.includes("/auth/refresh"));
  const response =
    serializesAuthSession && typeof navigator !== "undefined" && navigator.locks?.request
      ? await navigator.locks.request("madar-auth-session", runFetch)
      : await runFetch();

  const responseToken = response.headers.get(CSRF_HEADER_NAME);

  if (responseToken) {
    setCsrfToken(responseToken);
  }

  return response;
};
