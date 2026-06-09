export const API_BASE_URL = import.meta.env.VITE_API_URL || "/api";
export const USER_STATUS_PATH = import.meta.env.VITE_USER_STATUS_PATH || "/auth/user_status";

export const getApiUrl = (path) => `${API_BASE_URL}${path}`;

const parseJsonResponse = async (response) => {
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;

  if (!response.ok) {
    const error = new Error(data?.detail || data?.message || "Request failed");
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
};

export const fetchCurrentBackendUser = async () => {
  const response = await fetch(getApiUrl(USER_STATUS_PATH), {
    method: "GET",
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) return null;

  const data = await response.json();
  return data?.user || null;
};

const getUserScopedPath = async (userId, path) => {
  const scopedUserId = userId || (await fetchCurrentBackendUser())?.id;

  if (!scopedUserId) {
    throw new Error("Could not resolve current user id");
  }

  return `/users/${encodeURIComponent(scopedUserId)}${path}`;
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
    : `backend_${backendUser?.id || "current"}`,
  name: getBackendUserDisplayName(backendUser),
  email: backendUser?.email || "",
  roleId,
  status: "Active",
  lastSeen: "Now",
  isCurrentUser: true,
  backendUserId: backendUser?.id || "",
  authId: backendUser?.auth_id || "",
});

export const listBuilderProjects = async () => {
  const response = await fetch(getApiUrl("/builder/projects"), {
    method: "GET",
    credentials: "include",
    cache: "no-store",
  });

  const data = await parseJsonResponse(response);
  return data?.projects || [];
};

export const fetchBuilderProject = async (projectId) => {
  const response = await fetch(getApiUrl(`/builder/projects/${projectId}`), {
    method: "GET",
    credentials: "include",
    cache: "no-store",
  });

  const data = await parseJsonResponse(response);
  return data?.project || null;
};

export const createBuilderProject = async ({ name, slug, draft_schema }) => {
  const response = await fetch(getApiUrl("/builder/projects"), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, slug, draft_schema }),
  });

  const data = await parseJsonResponse(response);
  return data?.project || null;
};

export const updateBuilderProject = async (projectId, payload) => {
  const response = await fetch(getApiUrl(`/builder/projects/${projectId}`), {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await parseJsonResponse(response);
  return data?.project || null;
};

export const publishBuilderProject = async (projectId) => {
  const response = await fetch(getApiUrl(`/builder/projects/${projectId}/publish`), {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });

  const data = await parseJsonResponse(response);
  return data?.project || null;
};

export const fetchWebsiteSettings = async (userId) => {
  const response = await fetch(getApiUrl(await getUserScopedPath(userId, "/website/settings")), {
    method: "GET",
    credentials: "include",
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
  if (offset !== undefined && offset !== null) params.set("offset", String(offset));

  const query = params.toString();
  const response = await fetch(
    getApiUrl(`/builder/projects/${projectId}/form-submissions${query ? `?${query}` : ""}`),
    {
      method: "GET",
      credentials: "include",
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
  if (offset !== undefined && offset !== null) params.set("offset", String(offset));

  const query = params.toString();
  const response = await fetch(
    getApiUrl(`/builder/projects/${projectId}/form-submissions${query ? `?${query}` : ""}`),
    {
      method: "GET",
      credentials: "include",
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
  const response = await fetch(
    getApiUrl(`/builder/projects/${projectId}/form-submissions/${submissionId}`),
    {
      method: "PUT",
      credentials: "include",
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

export const fetchPublicSite = async (subdomain) => {
  const response = await fetch(getApiUrl(`/public/sites/${subdomain}`), {
    method: "GET",
    cache: "no-store",
  });

  const data = await parseJsonResponse(response);
  return data || null;
};
