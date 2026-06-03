export const API_BASE_URL = import.meta.env.VITE_API_URL || "/api";
export const USER_INFO_PATH = import.meta.env.VITE_USER_INFO_PATH || "/user/info";

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
  const response = await fetch(getApiUrl(USER_INFO_PATH), {
    method: "POST",
    credentials: "include",
    cache: "no-store",
  });

  if (!response.ok) return null;

  const data = await response.json();
  return data?.user || null;
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

export const fetchPublicSite = async (subdomain) => {
  const response = await fetch(getApiUrl(`/public/sites/${subdomain}`), {
    method: "GET",
    cache: "no-store",
  });

  const data = await parseJsonResponse(response);
  return data || null;
};
