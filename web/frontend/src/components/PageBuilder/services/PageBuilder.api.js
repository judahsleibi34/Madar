import { clearEcommerceAdminCache, loadEcommerceAdminResource } from "../../DashboardBuilder/utils/ecommerceAdminCache";
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

export const listBuilderProjects = async ({ limit = 20, offset = 0 } = {}) => {
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const response = await apiFetch(getApiUrl(`/builder/projects?${query}`), {
    method: "GET",
    cache: "no-store",
  });

  const data = await parseJsonResponse(response);
  const projects = Array.isArray(data?.projects) ? data.projects : [];
  return {
    projects,
    pagination: {
      limit: Number(data?.pagination?.limit ?? limit),
      offset: Number(data?.pagination?.offset ?? offset),
      count: Number(data?.pagination?.count ?? projects.length),
      has_more: Boolean(data?.pagination?.has_more),
    },
  };
};

export const fetchBuilderStorageUsage = async () => {
  const response = await apiFetch(getApiUrl("/builder/storage/usage"), {
    method: "GET",
    cache: "no-store",
  });
  const data = await parseJsonResponse(response);
  return (
    data?.storage || {
      used_bytes: 0,
      reserved_bytes: 0,
      quota_bytes: 0,
    }
  );
};

export const listBuilderReservations = async ({
  status = "",
  projectId = "",
  limit = 100,
  offset = 0,
} = {}) => {
  const query = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  if (status) query.set("status", status);
  if (projectId) query.set("project_id", projectId);

  const response = await apiFetch(
    getApiUrl("/builder/reservations?" + query.toString()),
    {
      method: "GET",
      cache: "no-store",
    }
  );
  const data = await parseJsonResponse(response);
  const reservations = Array.isArray(data?.reservations)
    ? data.reservations
    : Array.isArray(data?.items)
      ? data.items
      : [];

  return {
    reservations,
    pagination: {
      limit: Number(data?.pagination?.limit ?? limit),
      offset: Number(data?.pagination?.offset ?? offset),
      count: Number(data?.pagination?.count ?? reservations.length),
      has_more: Boolean(data?.pagination?.has_more),
    },
  };
};

export const fetchCalendarWorkspace = async ({ start, end, force = false }) => {
  const query = new URLSearchParams({ start, end });
  const response = await apiFetch(
    getApiUrl("/calendar/bootstrap?" + query.toString()),
    {
      method: "GET",
      cache: "no-store",
      headers: force ? { "X-Calendar-Cache-Bypass": "1" } : undefined,
    }
  );
  return parseJsonResponse(response);
};

export const createCalendar = async (calendar) => {
  const response = await apiFetch(getApiUrl("/calendar/calendars"), {
    method: "POST",
    headers: builderWriteHeaders(),
    body: JSON.stringify(calendar),
  });
  return (await parseJsonResponse(response))?.calendar;
};

export const createCalendarEvent = async (event) => {
  const response = await apiFetch(getApiUrl("/calendar/events"), {
    method: "POST",
    headers: builderWriteHeaders(),
    body: JSON.stringify(event),
  });
  return parseJsonResponse(response);
};

export const updateCalendarEvent = async (
  eventId,
  event,
  scope = "event",
  occurrenceStart = ""
) => {
  const query = new URLSearchParams({ scope });
  if (occurrenceStart) query.set("occurrence_start", occurrenceStart);
  const response = await apiFetch(
    getApiUrl(`/calendar/events/${encodeURIComponent(eventId)}?${query}`),
    {
      method: "PUT",
      headers: builderWriteHeaders(),
      body: JSON.stringify(event),
    }
  );
  return parseJsonResponse(response);
};

export const deleteCalendarEvent = async (
  eventId,
  expectedVersion,
  scope = "event",
  occurrenceStart = ""
) => {
  const query = new URLSearchParams({
    expected_version: String(expectedVersion),
    scope,
  });
  if (occurrenceStart) query.set("occurrence_start", occurrenceStart);
  const response = await apiFetch(
    getApiUrl(`/calendar/events/${encodeURIComponent(eventId)}?${query}`),
    { method: "DELETE", headers: builderWriteHeaders() }
  );
  return parseJsonResponse(response);
};

export const fetchCalendarEventHistory = async (eventId) => {
  const response = await apiFetch(
    getApiUrl(`/calendar/events/${encodeURIComponent(eventId)}/history`),
    { method: "GET", cache: "no-store" }
  );
  return (await parseJsonResponse(response))?.history || [];
};

export const createCalendarTask = async (task) => {
  const response = await apiFetch(getApiUrl("/calendar/tasks"), {
    method: "POST",
    headers: builderWriteHeaders(),
    body: JSON.stringify(task),
  });
  return (await parseJsonResponse(response))?.task;
};

export const updateCalendarTask = async (taskId, task, expectedVersion) => {
  const query = new URLSearchParams({ expected_version: String(expectedVersion) });
  const response = await apiFetch(
    getApiUrl(`/calendar/tasks/${encodeURIComponent(taskId)}?${query}`),
    {
      method: "PUT",
      headers: builderWriteHeaders(),
      body: JSON.stringify(task),
    }
  );
  return (await parseJsonResponse(response))?.task;
};

export const archiveCalendarTask = async (taskId, expectedVersion) => {
  const query = new URLSearchParams({ expected_version: String(expectedVersion) });
  const response = await apiFetch(
    getApiUrl(`/calendar/tasks/${encodeURIComponent(taskId)}/archive?${query}`),
    { method: "POST", headers: builderWriteHeaders() }
  );
  return (await parseJsonResponse(response))?.task;
};

export const fetchArchivedCalendarTasks = async () => {
  const response = await apiFetch(getApiUrl("/calendar/tasks/archived"), {
    method: "GET",
    cache: "no-store",
  });
  return (await parseJsonResponse(response))?.tasks || [];
};

export const syncCalendarTask = async (taskId, connectionId) => {
  const response = await apiFetch(
    getApiUrl(`/calendar/tasks/${encodeURIComponent(taskId)}/sync`),
    {
      method: "POST",
      headers: builderWriteHeaders(),
      body: JSON.stringify({ connection_id: connectionId }),
    }
  );
  return (await parseJsonResponse(response))?.task;
};

export const unlinkCalendarTaskSync = async (taskId) => {
  const response = await apiFetch(
    getApiUrl(`/calendar/tasks/${encodeURIComponent(taskId)}/sync`),
    { method: "DELETE", headers: builderWriteHeaders() }
  );
  return (await parseJsonResponse(response))?.task;
};

export const deleteCalendarTask = async (taskId, mode = "local_only") => {
  const query = new URLSearchParams({ mode });
  const response = await apiFetch(
    getApiUrl(`/calendar/tasks/${encodeURIComponent(taskId)}?${query}`),
    { method: "DELETE", headers: builderWriteHeaders() }
  );
  return parseJsonResponse(response);
};

export const createCalendarConnection = async (connection) => {
  const response = await apiFetch(getApiUrl("/calendar/connections"), {
    method: "POST",
    headers: builderWriteHeaders(),
    body: JSON.stringify(connection),
  });
  return parseJsonResponse(response);
};

export const authorizeCalendarConnection = async (connectionId) => {
  const response = await apiFetch(
    getApiUrl(`/calendar/connections/${encodeURIComponent(connectionId)}/authorize`),
    { method: "POST", headers: builderWriteHeaders() }
  );
  return (await parseJsonResponse(response))?.authorization_url || "";
};

export const upgradeCalendarConnection = async (connectionId) => {
  const response = await apiFetch(
    getApiUrl(`/calendar/connections/${encodeURIComponent(connectionId)}/upgrade`),
    { method: "POST", headers: builderWriteHeaders() }
  );
  return (await parseJsonResponse(response))?.authorization_url || "";
};

export const syncCalendarConnection = async (connectionId) => {
  const response = await apiFetch(
    getApiUrl(`/calendar/connections/${encodeURIComponent(connectionId)}/sync`),
    { method: "POST", headers: builderWriteHeaders() }
  );
  return parseJsonResponse(response);
};

export const setCalendarInboundSync = async (connectionId, enabled) => {
  const response = await apiFetch(
    getApiUrl(`/calendar/connections/${encodeURIComponent(connectionId)}/inbound`),
    {
      method: "PATCH",
      headers: builderWriteHeaders(),
      body: JSON.stringify({ enabled: Boolean(enabled) }),
    }
  );
  return parseJsonResponse(response);
};

export const removeCalendarConnection = async (connectionId) => {
  const response = await apiFetch(
    getApiUrl(`/calendar/connections/${encodeURIComponent(connectionId)}`),
    { method: "DELETE", headers: builderWriteHeaders() }
  );
  return parseJsonResponse(response);
};

export const disconnectCalendarConnection = async (connectionId) => {
  const response = await apiFetch(
    getApiUrl(`/calendar/connections/${encodeURIComponent(connectionId)}/disconnect`),
    { method: "POST", headers: builderWriteHeaders() }
  );
  return parseJsonResponse(response);
};

export const getCalendarExportUrl = ({ start, end, calendarId = "" }) => {
  const query = new URLSearchParams({ start, end });
  if (calendarId) query.set("calendar_id", calendarId);
  return getApiUrl("/calendar/export.ics?" + query.toString());
};

export const importCalendarIcs = async ({ calendarId, content }) => {
  const response = await apiFetch(getApiUrl("/calendar/import.ics"), {
    method: "POST",
    headers: builderWriteHeaders(),
    body: JSON.stringify({ calendar_id: calendarId, content }),
  });
  return parseJsonResponse(response);
};

export const resolveCalendarInvitation = async (reviewId, disposition) => {
  const query = new URLSearchParams({ disposition });
  const response = await apiFetch(
    getApiUrl(`/calendar/invitation-reviews/${encodeURIComponent(reviewId)}?${query}`),
    { method: "POST", headers: builderWriteHeaders() }
  );
  return parseJsonResponse(response);
};
export const fetchBuilderProject = async (projectId) => {
  const response = await apiFetch(getApiUrl(`/builder/projects/${projectId}`), {
    method: "GET",
    cache: "no-store",
  });

  const data = await parseJsonResponse(response);
  return data?.project || null;
};

export const fetchWeeklyScreenTime = async (projectId = "", period = "week") => {
  const query = new URLSearchParams();
  if (projectId) query.set("project_id", projectId);
  query.set("period", period);
  const suffix = query.toString() ? "?" + query.toString() : "";
  const response = await apiFetch(getApiUrl("/screen-time/weekly" + suffix), {
    method: "GET",
    cache: "no-store",
  });
  return parseJsonResponse(response);
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

export const updateBuilderSiteBinding = async (projectId) => {
  const response = await apiFetch(getApiUrl("/builder/site-binding"), {
    method: "PUT",
    headers: builderWriteHeaders(),
    body: JSON.stringify({ project_id: projectId }),
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

export const fetchWebsiteSettings = (scope = "authenticated", { force = false } = {}) =>
  loadEcommerceAdminResource(scope, "website-settings", async () => {
    const response = await apiFetch(getApiUrl("/website/settings"), { method: "GET", cache: "no-store" });
    const data = await parseJsonResponse(response);
    return data?.website || null;
  }, { force });

export const updateWebsiteSettings = async (settings) => {
  const response = await apiFetch(getApiUrl("/website/settings"), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });

  const data = await parseJsonResponse(response);
  clearEcommerceAdminCache(null, "website-settings");
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

export const fetchBuilderFormDraftsPage = async (
  projectId,
  { form_id, limit = 20, offset = 0 } = {}
) => {
  const params = new URLSearchParams();
  if (form_id) params.set("form_id", form_id);
  if (limit !== undefined && limit !== null) params.set("limit", String(limit));
  if (offset !== undefined && offset !== null) params.set("offset", String(offset));
  const query = params.toString();
  const response = await apiFetch(
    getApiUrl(`/builder/projects/${projectId}/form-drafts${query ? `?${query}` : ""}`),
    { method: "GET", cache: "no-store" }
  );
  const data = await parseJsonResponse(response);
  const drafts = data?.items || data?.drafts || [];
  return {
    submissions: drafts,
    pagination: data?.pagination || {
      limit,
      offset,
      count: drafts.length,
      has_more: drafts.length >= limit,
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

export const updateBuilderFormRecord = async (
  projectId,
  recordId,
  answers,
  { incomplete = false } = {}
) => {
  const collection = incomplete ? "form-drafts" : "form-submissions";
  const response = await apiFetch(
    getApiUrl(`/builder/projects/${projectId}/${collection}/${recordId}`),
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    }
  );

  const data = await parseJsonResponse(response);
  return data?.record || data?.draft || data?.submission || null;
};

export const deleteBuilderFormRecord = async (
  projectId,
  recordId,
  { incomplete = false } = {}
) => {
  const collection = incomplete ? "form-drafts" : "form-submissions";
  const response = await apiFetch(
    getApiUrl(`/builder/projects/${projectId}/${collection}/${recordId}`),
    { method: "DELETE" }
  );
  return parseJsonResponse(response);
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
