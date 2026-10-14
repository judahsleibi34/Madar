import { apiFetch, createApiError, getApiUrl } from "../../../utils/apiClient";

const parseJsonResponse = async (response) => {
  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text ? { message: text } : null;
  }
  if (!response.ok) throw createApiError(response, data);
  return data;
};

// The hosted-tenant entry starts the runtime's primary read while the route
// code is still downloading. The runtime's own fetch adopts that in-flight
// request instead of issuing a second one. Entries are tenant/form scoped,
// single-page-load only, and expire quickly so they are never served as a
// cache.
const EARLY_PUBLIC_READ_TTL_MS = 10_000;
const earlyPublicReads = new Map();

const startEarlyPublicRead = (key, load) => {
  if (earlyPublicReads.has(key)) return;
  const promise = load();
  promise.catch(() => {}); // The adopting caller owns error presentation.
  earlyPublicReads.set(key, { promise, startedAt: Date.now() });
};

const adoptEarlyPublicRead = (key) => {
  const entry = earlyPublicReads.get(key);
  if (!entry) return null;
  if (Date.now() - entry.startedAt > EARLY_PUBLIC_READ_TTL_MS) {
    earlyPublicReads.delete(key);
    return null;
  }
  // Keep the entry until the current task ends so React StrictMode's
  // synchronous effect replay adopts the same request.
  queueMicrotask(() => earlyPublicReads.delete(key));
  return entry.promise;
};

export const submitPublicFormSubmission = async (
  subdomain,
  formId,
  payload,
  { idempotencyKey = "" } = {}
) => {
  const cleanKey = String(idempotencyKey || "").slice(0, 128);
  const response = await apiFetch(
    getApiUrl(`/public/sites/${subdomain}/forms/${formId}/submissions`),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(cleanKey ? { "Idempotency-Key": cleanKey } : {}),
      },
      body: JSON.stringify({
        ...payload,
        ...(cleanKey ? { idempotency_key: cleanKey } : {}),
      }),
    }
  );

  return parseJsonResponse(response);
};

export const savePublicFormDraft = async (subdomain, formId, payload) => {
  const response = await apiFetch(
    getApiUrl(`/public/sites/${subdomain}/forms/${encodeURIComponent(formId)}/drafts`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  const data = await parseJsonResponse(response);
  return data?.draft || null;
};

export const listPublicFormDrafts = async (subdomain, formId) => {
  const response = await apiFetch(
    getApiUrl(
      `/public/sites/${subdomain}/forms/${encodeURIComponent(formId)}/drafts`
    ),
    { method: "GET", cache: "no-store" }
  );
  const data = await parseJsonResponse(response);
  return Array.isArray(data?.drafts) ? data.drafts : [];
};

export const fetchPublicFormDraft = async (subdomain, formId, resumeToken) => {
  const response = await apiFetch(
    getApiUrl(
      `/public/sites/${subdomain}/forms/${encodeURIComponent(formId)}/drafts/${encodeURIComponent(resumeToken)}`
    ),
    { method: "GET", cache: "no-store" }
  );
  const data = await parseJsonResponse(response);
  return data?.draft || null;
};

export const startPublicQuizAttempt = async (subdomain, formId, payload = {}) => {
  const response = await apiFetch(
    getApiUrl(`/public/sites/${subdomain}/forms/${formId}/attempts`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  return parseJsonResponse(response);
};

export const finalizePublicQuizAttempt = async (subdomain, formId, attemptId, answers) => {
  const response = await apiFetch(
    getApiUrl(`/public/sites/${subdomain}/forms/${formId}/attempts/${attemptId}/finalize`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    }
  );
  return parseJsonResponse(response);
};

export const submitPublicBuilderEvent = async (
  subdomain,
  payload,
  { idempotencyKey = "" } = {}
) => {
  const cleanKey = String(idempotencyKey || "").slice(0, 128);
  const response = await apiFetch(
    getApiUrl(`/public/sites/${subdomain}/events`),
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(cleanKey ? { "Idempotency-Key": cleanKey } : {}),
      },
      body: JSON.stringify({
        ...payload,
        ...(cleanKey ? { idempotency_key: cleanKey } : {}),
      }),
    }
  );

  return parseJsonResponse(response);
};

export const fetchPublicSite = async (subdomain) => {
  const response = await apiFetch(getApiUrl(`/public/sites/${subdomain}`), {
    method: "GET",
    cache: "no-store",
  });

  const data = await parseJsonResponse(response);
  return data || null;
};

export const fetchPublicSiteBootstrap = async (subdomain) => {
  const response = await apiFetch(getApiUrl(`/public/sites/${subdomain}/bootstrap`), {
    method: "GET",
    cache: "no-store",
  });

  const data = await parseJsonResponse(response);
  return data || null;
};

// Initial hosted-site response: publication, filtered schema, and visitor state
// are resolved together. The lightweight bootstrap remains available for polling.
const loadPublicSiteRuntime = async (subdomain) => {
  const response = await apiFetch(getApiUrl(`/public/sites/${subdomain}/runtime`), {
    method: "GET",
    cache: "no-store",
  });
  return (await parseJsonResponse(response)) || null;
};

export const fetchPublicSiteRuntime = (subdomain) =>
  adoptEarlyPublicRead(`runtime:${subdomain}`) || loadPublicSiteRuntime(subdomain);

export const prefetchPublicSiteRuntime = (subdomain) =>
  startEarlyPublicRead(`runtime:${subdomain}`, () => loadPublicSiteRuntime(subdomain));

export const fetchProtectedSitePage = async (subdomain, pageReference) => {
  const normalizedReference = String(pageReference || "").replace(/^\/+/, "");
  const response = await apiFetch(
    getApiUrl(
      `/public/sites/${subdomain}/pages/${encodeURIComponent(normalizedReference)}`
    ),
    {
      method: "GET",
      cache: "no-store",
    }
  );
  return parseJsonResponse(response);
};

export const fetchPublicForm = (subdomain, formId) =>
  adoptEarlyPublicRead(`form:${subdomain}:${formId}`) || loadPublicForm(subdomain, formId);

export const prefetchPublicForm = (subdomain, formId) =>
  startEarlyPublicRead(`form:${subdomain}:${formId}`, () => loadPublicForm(subdomain, formId));

const loadPublicForm = async (subdomain, formId) => {
  const response = await apiFetch(
    getApiUrl(`/public/sites/${subdomain}/forms/${encodeURIComponent(formId)}`),
    {
      method: "GET",
      cache: "no-store",
    }
  );

  const data = await parseJsonResponse(response);
  return data || null;
};

export const registerTenantVisitor = async (subdomain, payload) => {
  const response = await apiFetch(getApiUrl(`/public/sites/${subdomain}/auth/register`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
};

export const loginTenantVisitor = async (subdomain, payload) => {
  const response = await apiFetch(getApiUrl(`/public/sites/${subdomain}/auth/login`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseJsonResponse(response);
};

export const getTenantVisitorStatus = async (subdomain) => {
  const response = await apiFetch(getApiUrl(`/public/sites/${subdomain}/auth/status`), {
    method: "GET",
    cache: "no-store",
  });
  return parseJsonResponse(response);
};

export const logoutTenantVisitor = async (subdomain) => {
  const response = await apiFetch(getApiUrl(`/public/sites/${subdomain}/auth/logout`), {
    method: "POST",
  });
  return parseJsonResponse(response);
};
