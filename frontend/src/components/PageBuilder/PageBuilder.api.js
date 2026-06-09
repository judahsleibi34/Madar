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

  let data = null;

  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text ? { message: text } : null;
  }

  if (!response.ok) {
    const error = new Error(data?.detail || data?.message || "Request failed");
    error.status = response.status;
    error.data = data;
    throw error;
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
  const response = await fetch(getApiUrl(USER_STATUS_PATH), {
    method: "GET",
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) return null;

  const data = await response.json();
  return normalizeBackendUserFromStatus(data);
};

const getUserScopedPath = async (userId, path) => {
  const backendUser = userId ? null : await fetchCurrentBackendUser();
  const scopedUserId = userId || backendUser?.id || backendUser?.user_id;

  if (!scopedUserId) {
    throw new Error("Could not resolve current user id");
  }

  return `/users/${encodeURIComponent(scopedUserId)}${ensureLeadingSlash(path)}`;
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

export const listBuilderProjects = async (userId) => {
  const response = await fetch(
    getApiUrl(await getUserScopedPath(userId, "/builder/projects")),
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    }
  );

  const data = await parseJsonResponse(response);
  return data?.projects || [];
};

export const fetchBuilderProject = async (projectId, userId) => {
  const response = await fetch(
    getApiUrl(await getUserScopedPath(userId, `/builder/projects/${projectId}`)),
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    }
  );

  const data = await parseJsonResponse(response);
  return data?.project || null;
};

export const createBuilderProject = async (
  { name, slug, draft_schema },
  userId
) => {
  const response = await fetch(
    getApiUrl(await getUserScopedPath(userId, "/builder/projects")),
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, slug, draft_schema }),
    }
  );

  const data = await parseJsonResponse(response);
  return data?.project || null;
};

export const updateBuilderProject = async (projectId, payload, userId) => {
  const response = await fetch(
    getApiUrl(await getUserScopedPath(userId, `/builder/projects/${projectId}`)),
    {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );

  const data = await parseJsonResponse(response);
  return data?.project || null;
};

export const publishBuilderProject = async (projectId, userId) => {
  const response = await fetch(
    getApiUrl(
      await getUserScopedPath(userId, `/builder/projects/${projectId}/publish`)
    ),
    {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    }
  );

  const data = await parseJsonResponse(response);
  return data?.project || null;
};

export const fetchWebsiteSettings = async (userId) => {
  const response = await fetch(
    getApiUrl(await getUserScopedPath(userId, "/website/settings")),
    {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    }
  );

  const data = await parseJsonResponse(response);
  return data?.website || null;
};

export const fetchBuilderFormSubmissions = async (
  projectId,
  { form_id, limit = 100, offset = 0, user_id } = {}
) => {
  const params = new URLSearchParams();

  if (form_id) params.set("form_id", form_id);
  if (limit !== undefined && limit !== null) params.set("limit", String(limit));
  if (offset !== undefined && offset !== null)
    params.set("offset", String(offset));

  const query = params.toString();

  const response = await fetch(
    getApiUrl(
      await getUserScopedPath(
        user_id,
        `/builder/projects/${projectId}/form-submissions${
          query ? `?${query}` : ""
        }`
      )
    ),
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
  { form_id, limit = 20, offset = 0, user_id } = {}
) => {
  const params = new URLSearchParams();

  if (form_id) params.set("form_id", form_id);
  if (limit !== undefined && limit !== null) params.set("limit", String(limit));
  if (offset !== undefined && offset !== null)
    params.set("offset", String(offset));

  const query = params.toString();

  const response = await fetch(
    getApiUrl(
      await getUserScopedPath(
        user_id,
        `/builder/projects/${projectId}/form-submissions${
          query ? `?${query}` : ""
        }`
      )
    ),
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