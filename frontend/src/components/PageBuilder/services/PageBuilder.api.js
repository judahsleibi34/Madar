import { apiFetch, createApiError } from "../../../utils/apiClient";
import { getPersistableProject } from "../core/PageBuilder.editorState";

export const BUILDER_CLIENT_CONTRACT = "cloud-draft-v1";
const builderWriteHeaders = () => ({
  "Content-Type": "application/json",
  "X-Madar-Builder-Contract": BUILDER_CLIENT_CONTRACT,
});

export const API_BASE_URL = import.meta.env.VITE_API_URL || "/api";
export const USER_STATUS_PATH =
  import.meta.env.VITE_USER_STATUS_PATH || "/auth/user_status";

const trimTrailingSlash = (value) => String(value || "").replace(/\/+$/, "");
const ensureLeadingSlash = (value) =>
  String(value || "").startsWith("/") ? String(value || "") : `/${value || ""}`;

export const getApiUrl = (path) =>
  `${trimTrailingSlash(API_BASE_URL)}${ensureLeadingSlash(path)}`;

const parseJsonResponse = async (response) => {
  const text = await response.text();

  let data;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text ? { message: text } : null;
  }

  if (!response.ok) {
    throw createApiError(response, data);
  }

  return data;
};

const normalizeBackendUserFromStatus = (data) => {
  if (!data) return null;

  const user = data?.user || data;

  const loggedIn =
    data?.logged_in === true ||
    data?.authenticated === true ||
    Boolean(data?.user);

  if (!loggedIn) return null;

  const id = user?.id || user?.user_id;

  if (!id) return null;

  return {
    ...user,
    id,
    auth_id: user?.auth_id || user?.authId || "",
    tenant_id: user?.tenant_id || user?.tenantId || "",
    user_type:
      user?.user_type ||
      user?.role ||
      (user?.admin === true || user?.is_admin === true ? "admin" : "user"),
  };
};

export const fetchCurrentBackendUser = async () => {
  const response = await apiFetch(getApiUrl(USER_STATUS_PATH), {
    method: "GET",
    cache: "no-store",
  });

  if (!response.ok) return null;

  const data = await response.json();
  return normalizeBackendUserFromStatus(data);
};

export const getBackendUserDisplayName = (user) => {
  const firstName = user?.first_name || "";
  const lastName = user?.last_name || "";
  const fullName = `${firstName} ${lastName}`.trim();

  return user?.name || fullName || "You";
};

export const mapBackendUserToBuilderUser = (backendUser, roleId = "") => ({
  id: backendUser?.auth_id
    ? `auth_${backendUser.auth_id}`
    : `backend_${backendUser?.id || backendUser?.user_id || "current"}`,
  name: getBackendUserDisplayName(backendUser),
  email: backendUser?.email || "",
  roleId,
  status: "Active",
  lastSeen: "Now",
  isCurrentUser: true,
  backendUserId: backendUser?.id || backendUser?.user_id || "",
  authId: backendUser?.auth_id || backendUser?.authId || "",
});

export const listBuilderProjects = async () => {
  const response = await apiFetch(getApiUrl("/builder/projects"), {
    method: "GET",
    cache: "no-store",
  });

  const data = await parseJsonResponse(response);
  return data?.projects || [];
};

export const fetchBuilderProject = async (projectId) => {
  const response = await apiFetch(getApiUrl(`/builder/projects/${projectId}`), {
    method: "GET",
    cache: "no-store",
  });

  const data = await parseJsonResponse(response);
  return data?.project || null;
};

export const fetchBuilderSiteMembers = async (projectId) => {
  const response = await apiFetch(
    getApiUrl(`/builder/projects/${projectId}/site-members`),
    { method: "GET", cache: "no-store" }
  );
  const data = await parseJsonResponse(response);
  return data?.members || [];
};

export const createBuilderSiteMember = async (projectId, member) => {
  const response = await apiFetch(
    getApiUrl(`/builder/projects/${projectId}/site-members`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(member),
    }
  );
  const data = await parseJsonResponse(response);
  return data?.member || null;
};

export const updateBuilderSiteMember = async (projectId, membershipId, updates) => {
  const response = await apiFetch(
    getApiUrl(`/builder/projects/${projectId}/site-members/${membershipId}`),
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    }
  );
  const data = await parseJsonResponse(response);
  return data?.member || null;
};

export const deleteBuilderSiteMember = async (projectId, membershipId) => {
  const response = await apiFetch(
    getApiUrl(`/builder/projects/${projectId}/site-members/${membershipId}`),
    { method: "DELETE" }
  );
  return parseJsonResponse(response);
};

export const createBuilderProject = async ({ name, slug, draft_schema }) => {
  const response = await apiFetch(getApiUrl("/builder/projects"), {
    method: "POST",
    headers: builderWriteHeaders(),
    body: JSON.stringify({ name, slug, draft_schema: getPersistableProject(draft_schema) }),
  });

  const data = await parseJsonResponse(response);
  return data?.project || null;
};

export const updateBuilderProject = async (projectId, payload) => {
  const response = await apiFetch(getApiUrl(`/builder/projects/${projectId}`), {
    method: "PUT",
    headers: builderWriteHeaders(),
    body: JSON.stringify({
      ...payload,
      ...(payload?.draft_schema
        ? { draft_schema: getPersistableProject(payload.draft_schema) }
        : {}),
    }),
  });

  const data = await parseJsonResponse(response);
  return data?.project || null;
};

export const publishBuilderProject = async (projectId, expectedRevision = null) => {
  const response = await apiFetch(getApiUrl(`/builder/projects/${projectId}/publish`), {
    method: "POST",
    headers: builderWriteHeaders(),
    body: JSON.stringify(
      expectedRevision === null || expectedRevision === undefined
        ? {}
        : { expected_revision: expectedRevision }
    ),
  });

  return parseJsonResponse(response);
};

export const unpublishBuilderProject = async (projectId, expectedRevision = null) => {
  const response = await apiFetch(getApiUrl(`/builder/projects/${projectId}/unpublish`), {
    method: "POST",
    headers: builderWriteHeaders(),
    body: JSON.stringify(
      expectedRevision === null || expectedRevision === undefined
        ? {}
        : { expected_revision: expectedRevision }
    ),
  });

  return parseJsonResponse(response);
};

export const uploadBuilderAsset = async (file) => {
  const formData = new FormData();
  formData.append("file", file);

  const response = await apiFetch(getApiUrl("/builder/assets/upload"), {
    method: "POST",
    body: formData,
  });

  const data = await parseJsonResponse(response);
  return data?.asset_url || data?.url || "";
};

export const fetchWebsiteSettings = async () => {
  const response = await apiFetch(getApiUrl("/website/settings"), {
    method: "GET",
    cache: "no-store",
  });

  const data = await parseJsonResponse(response);
  return data?.website || null;
};

export const fetchBuilderFormSubmissions = async (
  projectId,
  { form_id, limit = 100, offset = 0 } = {}
) => {
  const params = new URLSearchParams();

  if (form_id) params.set("form_id", form_id);
  if (limit !== undefined && limit !== null) params.set("limit", String(limit));
  if (offset !== undefined && offset !== null)
    params.set("offset", String(offset));

  const query = params.toString();

  const response = await apiFetch(
    getApiUrl(`/builder/projects/${projectId}/form-submissions${query ? `?${query}` : ""}`),
    {
      method: "GET",
      cache: "no-store",
    }
  );

  const data = await parseJsonResponse(response);
  return data?.submissions || [];
};

export const fetchBuilderFormSubmissionsPage = async (
  projectId,
  { form_id, limit = 20, offset = 0 } = {}
) => {
  const params = new URLSearchParams();

  if (form_id) params.set("form_id", form_id);
  if (limit !== undefined && limit !== null) params.set("limit", String(limit));
  if (offset !== undefined && offset !== null)
    params.set("offset", String(offset));

  const query = params.toString();

  const response = await apiFetch(
    getApiUrl(`/builder/projects/${projectId}/form-submissions${query ? `?${query}` : ""}`),
    {
      method: "GET",
      cache: "no-store",
    }
  );

  const data = await parseJsonResponse(response);
  const submissions = data?.items || data?.submissions || [];

  return {
    submissions,
    pagination: data?.pagination || {
      limit,
      offset,
      count: submissions.length,
      has_more: submissions.length >= limit,
    },
  };
};

export const updateBuilderFormSubmissionStatus = async (
  projectId,
  submissionId,
  status
) => {
  const response = await apiFetch(
    getApiUrl(`/builder/projects/${projectId}/form-submissions/${submissionId}`),
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }
  );

  const data = await parseJsonResponse(response);
  return data?.submission || null;
};

export const submitPublicFormSubmission = async (subdomain, formId, payload) => {
  const response = await fetch(
    getApiUrl(`/public/sites/${subdomain}/forms/${formId}/submissions`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
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
  const response = await fetch(
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
  const response = await fetch(getApiUrl(`/public/sites/${subdomain}`), {
    method: "GET",
    cache: "no-store",
  });

  const data = await parseJsonResponse(response);
  return data || null;
};

export const fetchPublicForm = async (subdomain, formId) => {
  const response = await fetch(
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
