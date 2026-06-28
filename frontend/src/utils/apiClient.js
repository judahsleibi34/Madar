export const CSRF_HEADER_NAME = "X-CSRF-Token";
export const CSRF_COOKIE_NAME = "madar_csrf_token";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const API_URL = import.meta.env.VITE_API_URL || "/api";

let csrfToken = "";
let refreshSessionPromise = null;

const getApiUrl = (path) =>
  `${String(API_URL).replace(/\/+$/, "")}/${String(path).replace(/^\/+/, "")}`;

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
  const { skipAuthRefresh = false, ...fetchInit } = init;
  const method = String(fetchInit.method || "GET").toUpperCase();
  const headers = new Headers(fetchInit.headers || {});

  if (UNSAFE_METHODS.has(method) && !headers.has(CSRF_HEADER_NAME)) {
    const token = getCsrfToken();

    if (token) {
      headers.set(CSRF_HEADER_NAME, token);
    }
  }

  const runFetch = () => fetch(input, {
    ...fetchInit,
    method,
    credentials: fetchInit.credentials || "include",
    headers,
  });

  const inputUrl = typeof input === "string" ? input : input?.url || "";
  const isAuthRefresh = inputUrl.includes("/auth/refresh");
  const isAuthEndpoint =
    inputUrl.includes("/auth/login") ||
    inputUrl.includes("/auth/signup") ||
    inputUrl.includes("/auth/log_out") ||
    inputUrl.includes("/auth/user_status") ||
    isAuthRefresh;
  const serializesAuthSession =
    (method === "GET" && inputUrl.includes("/auth/user_status")) ||
    (method === "POST" && isAuthRefresh);

  const runSerializedFetch = async () =>
    serializesAuthSession && typeof navigator !== "undefined" && navigator.locks?.request
      ? await navigator.locks.request("madar-auth-session", runFetch)
      : await runFetch();

  const response = await runSerializedFetch();

  const responseToken = response.headers.get(CSRF_HEADER_NAME);

  if (responseToken) {
    setCsrfToken(responseToken);
  }

  if (
    response.status === 401 &&
    !isAuthEndpoint &&
    !skipAuthRefresh
  ) {
    if (!refreshSessionPromise) {
      refreshSessionPromise = apiFetch(getApiUrl("/auth/refresh"), {
        method: "POST",
        cache: "no-store",
        skipAuthRefresh: true,
      }).finally(() => {
        refreshSessionPromise = null;
      });
    }

    const refreshResponse = await refreshSessionPromise;

    if (refreshResponse.ok) {
      return apiFetch(input, {
        ...fetchInit,
        skipAuthRefresh: true,
      });
    }
  }

  return response;
};
