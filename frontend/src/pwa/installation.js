import { getMadarLaunchContext, isMadarPwaHost } from "./pwaContext";
import { apiFetch, getApiUrl, readApiError, readApiResponse } from "../utils/apiClient";

export const MADAR_INSTALLATION_STORAGE_KEY = "madar-app-installation-id:v1";
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

let volatileInstallationId = null;
let lastRegistrationSignature = null;
let registrationPromise = null;
let registrationQueue = Promise.resolve();

function createUuid(cryptoLike = globalThis.crypto) {
  if (typeof cryptoLike?.randomUUID === "function") return cryptoLike.randomUUID();
  if (typeof cryptoLike?.getRandomValues !== "function") return null;
  const bytes = cryptoLike.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((value) => value.toString(16).padStart(2, "0"));
  return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10).join("")}`;
}

export function getInstallationId({
  storage = globalThis.localStorage,
  cryptoLike = globalThis.crypto,
  locationLike = globalThis.location,
} = {}) {
  if (!isMadarPwaHost(locationLike)) return null;
  try {
    const stored = storage?.getItem(MADAR_INSTALLATION_STORAGE_KEY);
    if (stored && UUID_PATTERN.test(stored)) return stored;
  } catch {
    // A stable in-page fallback keeps registration coherent when storage is blocked.
  }
  if (!volatileInstallationId) volatileInstallationId = createUuid(cryptoLike);
  if (!volatileInstallationId) return null;
  try {
    storage?.setItem(MADAR_INSTALLATION_STORAGE_KEY, volatileInstallationId);
  } catch {
    // Storage denial is non-fatal; this identifier lasts for the current page only.
  }
  return volatileInstallationId;
}

export function rotateInstallationId({
  storage = globalThis.localStorage,
  cryptoLike = globalThis.crypto,
  locationLike = globalThis.location,
} = {}) {
  if (!isMadarPwaHost(locationLike)) return null;
  try {
    storage?.removeItem(MADAR_INSTALLATION_STORAGE_KEY);
  } catch {
    // Storage denial remains non-fatal.
  }
  volatileInstallationId = null;
  lastRegistrationSignature = null;
  registrationPromise = null;
  return getInstallationId({ storage, cryptoLike, locationLike });
}

export function detectPlatform(navigatorLike = globalThis.navigator) {
  const value = `${navigatorLike?.userAgentData?.platform || navigatorLike?.platform || navigatorLike?.userAgent || ""}`.toLowerCase();
  if (/iphone|ipad|ipod/.test(value) || (/mac/.test(value) && navigatorLike?.maxTouchPoints > 1)) return "ios";
  if (/android/.test(value)) return "android";
  if (/cros/.test(value)) return "chromeos";
  if (/win/.test(value)) return "windows";
  if (/mac/.test(value)) return "macos";
  if (/linux/.test(value)) return "linux";
  return "unknown";
}

export function getInstallationContext(windowLike = globalThis.window) {
  const launch = getMadarLaunchContext(windowLike);
  return {
    displayMode: launch.isIOSStandalone
      ? "ios_standalone"
      : launch.isStandalone ? "standalone" : "browser",
    platform: detectPlatform(windowLike?.navigator),
    notificationPermission: windowLike?.Notification?.permission || "unknown",
    installedConfirmed: launch.isStandalone,
  };
}

export async function registerInstallation({
  tenantId,
  force = false,
  installedConfirmed = false,
  windowLike = globalThis.window,
} = {}) {
  if (!tenantId || !isMadarPwaHost(windowLike?.location)) return null;
  const installationId = getInstallationId({
    storage: windowLike?.localStorage,
    cryptoLike: windowLike?.crypto,
    locationLike: windowLike?.location,
  });
  if (!installationId) return null;
  const context = getInstallationContext(windowLike);
  const payload = {
    installation_id: installationId,
    platform: context.platform,
    display_mode: context.displayMode,
    notification_permission: context.notificationPermission,
    installed_confirmed: Boolean(installedConfirmed || context.installedConfirmed),
  };
  const signature = `${tenantId}:${JSON.stringify(payload)}`;
  if (!force && signature === lastRegistrationSignature) return registrationPromise;

  lastRegistrationSignature = signature;
  const sendRegistration = async () => {
    const response = await apiFetch(getApiUrl("/installations/register"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await readApiResponse(response);
    if (!response.ok) {
      const error = new Error(readApiError(data, "Could not register installation."));
      error.status = response.status;
      throw error;
    }
    return { ...data, installationId };
  };
  // Serialize tenant transitions so an older tenant heartbeat cannot reach
  // the server after the newer one and leave routing metadata stale.
  registrationPromise = registrationQueue
    .catch(() => null)
    .then(sendRegistration);
  registrationQueue = registrationPromise;
  registrationPromise.catch(() => {
    if (lastRegistrationSignature === signature) lastRegistrationSignature = null;
  });
  return registrationPromise;
}

export function resetInstallationRegistrationForTests() {
  volatileInstallationId = null;
  lastRegistrationSignature = null;
  registrationPromise = null;
  registrationQueue = Promise.resolve();
}
