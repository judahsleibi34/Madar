export const API_URL = import.meta.env.VITE_API_URL || "/api";

export const readApiResponse = async (response) => {
  const contentType = response.headers.get("Content-Type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  const text = await response.text();

  return {
    detail: text || response.statusText || "The server returned an unreadable response.",
  };
};

let refreshSessionPromise = null;

export const refreshSession = async () => {
  if (!refreshSessionPromise) {
    refreshSessionPromise = fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
    }).finally(() => {
      refreshSessionPromise = null;
    });
  }

  return refreshSessionPromise;
};

export const authFetch = async (input, init = {}) => {
  const requestInit = {
    ...init,
    credentials: init.credentials || "include",
  };

  const response = await fetch(input, requestInit);

  if (response.status !== 401) {
    return response;
  }

  const refreshResponse = await refreshSession();

  if (!refreshResponse.ok) {
    return response;
  }

  return fetch(input, {
    ...requestInit,
    credentials: "include",
  });
};

export const getFriendlyExternalError = (detail) => {
  const message = String(detail || "");
  const lowerMessage = message.toLowerCase();

  if (
    lowerMessage.includes("google sheet") ||
    lowerMessage.includes("google returned")
  ) {
    return message.replace(/^Failed to read data:\s*/i, "");
  }

  if (
    lowerMessage.includes("http error 400") ||
    lowerMessage.includes("bad request")
  ) {
    return "The link could not be read. For Google Sheets, share it with anyone who has the link or publish it to the web, then paste the full sheet URL.";
  }

  if (lowerMessage.includes("could not detect data format")) {
    return "The link was reachable, but it does not look like CSV, Excel, JSON, or Google Sheets data.";
  }

  return message || "The external data could not be loaded.";
};
