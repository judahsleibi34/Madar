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
export const fetchPublicSiteRuntime = async (subdomain) => {
  const response = await apiFetch(getApiUrl(`/public/sites/${subdomain}/runtime`), {
    method: "GET",
    cache: "no-store",
  });
  return (await parseJsonResponse(response)) || null;
};

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

export const fetchPublicForm = async (subdomain, formId) => {
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
