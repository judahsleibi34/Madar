const productionLabels = new Set(["production", "prod", "main", "shared", "live"]);

function configuredProductionHosts(environment) {
  return String(environment.MADAR_E2E_PRODUCTION_HOSTS || "")
    .split(",")
    .map((host) => host.trim().toLowerCase())
    .filter(Boolean);
}

function isProductionHost(hostname, environment) {
  const host = hostname.toLowerCase().replace(/\.$/, "");
  if (host === "madar.com" || host.endsWith(".madar.com")) return true;
  return configuredProductionHosts(environment).some(
    (blocked) => host === blocked || host.endsWith(`.${blocked}`)
  );
}

export function assertIsolatedE2EEnvironment(environment = process.env) {
  if (environment.MADAR_E2E_CONFIRM_ISOLATED !== "YES") {
    throw new Error("MADAR_E2E_CONFIRM_ISOLATED must be exactly YES");
  }

  const rawBaseUrl = environment.MADAR_E2E_BASE_URL?.trim();
  if (!rawBaseUrl) throw new Error("MADAR_E2E_BASE_URL is required");

  let baseUrl;
  try {
    baseUrl = new URL(rawBaseUrl);
  } catch {
    throw new Error("MADAR_E2E_BASE_URL must be an absolute URL");
  }
  if (!["http:", "https:"].includes(baseUrl.protocol)) {
    throw new Error("MADAR_E2E_BASE_URL must use HTTP or HTTPS");
  }
  if (baseUrl.username || baseUrl.password) {
    throw new Error("MADAR_E2E_BASE_URL must not contain credentials");
  }
  if (isProductionHost(baseUrl.hostname, environment)) {
    throw new Error("MADAR_E2E_BASE_URL matches a forbidden production host");
  }

  const databaseId = environment.MADAR_E2E_DATABASE_ID?.trim().toLowerCase();
  if (!databaseId?.startsWith("madar_e2e_")) {
    throw new Error("MADAR_E2E_DATABASE_ID must start with madar_e2e_");
  }
  if ([...productionLabels].some((label) => databaseId.split(/[_-]/).includes(label))) {
    throw new Error("MADAR_E2E_DATABASE_ID contains a forbidden shared/production label");
  }

  const runId = environment.MADAR_E2E_RUN_ID?.trim();
  if (!runId || !/^[a-z0-9][a-z0-9_-]{7,63}$/i.test(runId)) {
    throw new Error("MADAR_E2E_RUN_ID must be a unique 8-64 character identifier");
  }
  if (environment.MADAR_E2E_MIGRATIONS_APPLIED_FROM_CLEAN !== "YES") {
    throw new Error("MADAR_E2E_MIGRATIONS_APPLIED_FROM_CLEAN must be exactly YES");
  }
  if (environment.MADAR_E2E_EXTERNAL_DELIVERY_DISABLED !== "YES") {
    throw new Error("MADAR_E2E_EXTERNAL_DELIVERY_DISABLED must be exactly YES");
  }

  return { baseUrl: baseUrl.origin, databaseId, runId };
}
