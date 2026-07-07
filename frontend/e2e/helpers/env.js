export const e2eEnv = {
  baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:5173",
  backendURL: process.env.E2E_BACKEND_URL || "",
  userEmail: process.env.E2E_USER_EMAIL || "",
  userPassword: process.env.E2E_USER_PASSWORD || "",
  adminEmail: process.env.E2E_ADMIN_EMAIL || "",
  adminPassword: process.env.E2E_ADMIN_PASSWORD || "",
};

export function hasUserCredentials() {
  return Boolean(e2eEnv.userEmail && e2eEnv.userPassword);
}

export function hasAdminCredentials() {
  return Boolean(e2eEnv.adminEmail && e2eEnv.adminPassword);
}

export function uniqueTestEmail(prefix = "madar-e2e") {
  const timestamp = new Date().toISOString().replace(/[-:.TZ]/g, "");
  const random = Math.random().toString(36).slice(2, 8);
  return `${prefix}+${timestamp}-${random}@example.test`;
}
