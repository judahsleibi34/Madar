export const CSRF_HEADER_NAME = "X-CSRF-Token";
export const CSRF_COOKIE_NAME = "madar_csrf_token";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
export const API_URL = import.meta.env.VITE_API_URL || "/api";

let csrfToken = "";
let refreshSessionPromise = null;
let selectedTenantId = null;
let tenantGeneration = 0;
export const getSelectedTenantId = () => selectedTenantId;
export const setSelectedTenantId = (value) => {
  const next = value == null ? null : Number(value);
  if (next !== null && (!Number.isSafeInteger(next) || next <= 0 || next > 2147483647)) throw new Error("Invalid workspace");
  if (next !== selectedTenantId) tenantGeneration += 1;
  selectedTenantId = next;
};
const isMadarApi = (input) => {
  try {
    const base = new URL(API_URL, globalThis.location?.origin || "http://localhost");
    const target = new URL(input, globalThis.location?.origin || "http://localhost");
    return target.origin === base.origin && (target.pathname === base.pathname || target.pathname.startsWith(base.pathname.replace(/\/+$/, "") + "/"));
  } catch { return false; }
};


export const getApiUrl = (path) =>
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

export const readApiResponse = async (response) => {
  const contentType = response.headers.get("Content-Type") || "";

  if (contentType.includes("application/json") || contentType.includes("+json")) {
    const data = await response.json().catch(() => null);
    syncCsrfTokenFromResponseData(data);
    return data;
  }

  return {
    detail: "The server returned an unexpected response.",
  };
};

export const readApiError = (data, fallback = "Request failed") => {
  if (typeof data?.detail?.message === "string" && data.detail.message.trim()) {
    return data.detail.message;
  }

  if (typeof data?.detail === "string" && data.detail.trim()) {
    return data.detail;
  }

  if (typeof data?.message === "string" && data.message.trim()) {
    return data.message;
  }

  if (Array.isArray(data?.detail)) {
    return data.detail
      .map((error) => error?.msg || "")
      .filter(Boolean)
      .join(" ") || fallback;
  }

  return fallback;
};

export const readApiErrorCode = (data) => {
  if (typeof data?.code === "string" && data.code.trim()) {
    return data.code;
  }

  if (typeof data?.detail?.code === "string" && data.detail.code.trim()) {
    return data.detail.code;
  }

  if (typeof data?.error?.code === "string" && data.error.code.trim()) {
    return data.error.code;
  }

  return "";
};

export const readApiErrorContext = (data) => {
  const context = data?.detail?.context ?? data?.context ?? data?.error?.context;

  return context && typeof context === "object" && !Array.isArray(context)
    ? context
    : {};
};

export const parseApiError = (data, fallback = "Request failed") => ({
  code: readApiErrorCode(data),
  message: readApiError(data, fallback),
  context: readApiErrorContext(data),
});

export const createApiError = (response, data, fallback = "Request failed") => {
  const parsed = parseApiError(data, fallback);
  const error = new Error(parsed.message);

  error.name = "ApiError";
  error.status = Number(response?.status || 0);
  error.code = parsed.code;
  error.context = parsed.context;
  error.data = data;

  return error;
};

const refreshCsrfToken = async () => {
  const response = await fetch(getApiUrl("/auth/user_status"), {
    method: "GET",
    cache: "no-store",
    credentials: "include",
  });

  if (!response.ok) return "";

  const responseToken = response.headers.get(CSRF_HEADER_NAME);

  if (responseToken) {
    return setCsrfToken(responseToken);
  }

  const data = await response.json().catch(() => null);
  syncCsrfTokenFromResponseData(data);
  return getCsrfToken();
};

const isInvalidCsrfResponse = async (response) => {
  if (response.status !== 403) return false;

  const data = await response.clone().json().catch(() => null);
  return data?.detail === "Invalid CSRF token";
};

export const apiFetch = async (input, init = {}) => {
  const { skipAuthRefresh = false, ...fetchInit } = init;
  const method = String(fetchInit.method || "GET").toUpperCase();
  const headers = new Headers(fetchInit.headers || {});
  const inputUrl = typeof input === "string" ? input : input?.url || "";
  const generation = tenantGeneration;
  const tenantScoped = isMadarApi(inputUrl);
  const assertCurrentTenant = () => {
    if (tenantScoped && generation !== tenantGeneration) throw new DOMException("Workspace changed", "AbortError");
  };
  if (tenantScoped && selectedTenantId !== null) headers.set("X-Madar-Tenant-ID", String(selectedTenantId));
  const isAuthRefresh = inputUrl.includes("/auth/refresh");
  const isAuthEndpoint =
    inputUrl.includes("/auth/login") ||
    inputUrl.includes("/auth/signup") ||
    inputUrl.includes("/auth/email-verification/") ||
    inputUrl.includes("/auth/forgot-password") ||
    inputUrl.includes("/auth/password-reset") ||
    inputUrl.includes("/auth/log_out") ||
    inputUrl.includes("/auth/user_status") ||
    isAuthRefresh;

  if (UNSAFE_METHODS.has(method) && !headers.has(CSRF_HEADER_NAME)) {
    const token = getCsrfToken() || (!isAuthEndpoint && !skipAuthRefresh
      ? await refreshCsrfToken()
      : "");

    if (token) {
      headers.set(CSRF_HEADER_NAME, token);
    }
  }

  const runFetch = (requestHeaders = headers) => {
    assertCurrentTenant();
    return fetch(input, {
    ...fetchInit,
    method,
    credentials: fetchInit.credentials || "include",
    headers: requestHeaders,
    });
  };

  const serializesAuthSession =
    (method === "GET" && inputUrl.includes("/auth/user_status")) ||
    (method === "POST" && isAuthRefresh);

  const runSerializedFetch = async (requestHeaders = headers) =>
    serializesAuthSession && typeof navigator !== "undefined" && navigator.locks?.request
      ? await navigator.locks.request("madar-auth-session", () => runFetch(requestHeaders))
      : await runFetch(requestHeaders);

  const response = await runSerializedFetch();
  assertCurrentTenant();
  if (response.status === 403 && tenantScoped) {
    const denied = await response.clone().json().catch(() => null);
    if (["entitlement_required", "storage_entitlement_required", "base_plan_required"].includes(denied?.detail?.code)) {
      window.dispatchEvent(new Event("madar:commercial-denied"));
    }
  }

  const responseToken = response.headers.get(CSRF_HEADER_NAME);

  if (responseToken) {
    setCsrfToken(responseToken);
  }

  if (
    UNSAFE_METHODS.has(method) &&
    !isAuthEndpoint &&
    !skipAuthRefresh &&
    await isInvalidCsrfResponse(response)
  ) {
    const refreshedToken = await refreshCsrfToken();
    assertCurrentTenant();

    if (refreshedToken) {
      return apiFetch(input, {
        ...fetchInit,
        skipAuthRefresh: true,
      });
    }
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
    assertCurrentTenant();

    if (refreshResponse.ok) {
      return apiFetch(input, {
        ...fetchInit,
        skipAuthRefresh: true,
      });
    }

    if (refreshResponse.status >= 500) {
      return refreshResponse.clone();
    }
  }

  if (
    response.status === 403 &&
    UNSAFE_METHODS.has(method) &&
    !isAuthEndpoint &&
    !skipAuthRefresh
  ) {
    const errorData = await response.clone().json().catch(() => null);
    const csrfRejected = errorData?.detail === "Invalid CSRF token";

    if (csrfRejected) {
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
    assertCurrentTenant();

      if (refreshResponse.ok) {
        const retryHeaders = new Headers(fetchInit.headers || {});
        const token = getCsrfToken();

        if (token) {
          retryHeaders.set(CSRF_HEADER_NAME, token);
        }

        return apiFetch(input, {
          ...fetchInit,
          headers: retryHeaders,
          skipAuthRefresh: true,
        });
      }

      if (refreshResponse.status >= 500) {
        return refreshResponse.clone();
      }
    }
  }

  assertCurrentTenant();
  return response;
};

const postJson = async (path, payload, init = {}) => {
  const { headers: initHeaders, ...fetchInit } = init;
  const response = await apiFetch(getApiUrl(path), {
    ...fetchInit,
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(initHeaders || {}),
    },
    body: JSON.stringify(payload),
  });

  const data = await readApiResponse(response);
  return { response, data };
};

export const postAuthJson = (path, payload, init = {}) =>
  postJson(path, payload, {
    skipAuthRefresh: true,
    ...init,
  });

export const postPublicJson = (path, payload, init = {}) =>
  postJson(path, payload, {
    skipAuthRefresh: true,
    ...init,
  });
