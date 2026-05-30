export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";
export const USER_INFO_PATH = import.meta.env.VITE_USER_INFO_PATH || "/user/info";

export const getApiUrl = (path) => `${API_BASE_URL}${path}`;

export const fetchCurrentBackendUser = async () => {
  const response = await fetch(getApiUrl(USER_INFO_PATH), {
    method: "POST",
    credentials: "include",
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