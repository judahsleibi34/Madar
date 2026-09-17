import { getMadarLaunchContext, isIOSDevice, isMadarPwaHost } from "./pwaContext";

let snapshot = {
  deferredPrompt: null,
  error: null,
  installed: false,
  lastOutcome: null,
  prompting: false,
};
let initializedWindow = null;
let beforeInstallPromptHandler = null;
let appInstalledHandler = null;
const listeners = new Set();
const installedListeners = new Set();

const publish = (patch) => {
  snapshot = { ...snapshot, ...patch };
  listeners.forEach((listener) => listener());
};

export function isChromiumInstallBrowser(windowLike = globalThis.window) {
  const navigatorLike = windowLike?.navigator;
  const brands = (navigatorLike?.userAgentData?.brands || [])
    .map((item) => item?.brand || "")
    .join(" ");
  const userAgent = navigatorLike?.userAgent || "";
  return /Chromium|Google Chrome|Microsoft Edge/i.test(brands)
    || /Chrome|CriOS|Edg|OPR|SamsungBrowser/i.test(userAgent);
}

export function getInstallPromptState(windowLike = globalThis.window) {
  const supportedHost = isMadarPwaHost(windowLike?.location);
  const installed = supportedHost && (
    snapshot.installed || getMadarLaunchContext(windowLike).isStandalone
  );
  const isIOS = supportedHost && isIOSDevice(windowLike);
  let status = "unsupported";
  if (!supportedHost) status = "unsupported";
  else if (installed) status = "installed";
  else if (snapshot.deferredPrompt) status = "prompt_available";
  else if (isIOS) status = "ios_manual";
  else if (isChromiumInstallBrowser(windowLike)) status = "manual_install_available";

  return {
    ...snapshot,
    installed,
    isIOS,
    status,
    supportedHost,
  };
}

export function initializeInstallPromptCapture(windowLike = globalThis.window) {
  if (!windowLike?.addEventListener || initializedWindow === windowLike) return;
  initializedWindow = windowLike;
  snapshot = {
    ...snapshot,
    installed: getMadarLaunchContext(windowLike).isStandalone,
  };

  beforeInstallPromptHandler = (event) => {
    if (!isMadarPwaHost(windowLike.location)) return;
    event.preventDefault();
    if (!getMadarLaunchContext(windowLike).isStandalone) {
      publish({ deferredPrompt: event, error: null, lastOutcome: null });
    }
  };
  appInstalledHandler = () => {
    publish({
      deferredPrompt: null,
      error: null,
      installed: true,
      lastOutcome: "accepted",
      prompting: false,
    });
    installedListeners.forEach((listener) => listener());
  };
  windowLike.addEventListener("beforeinstallprompt", beforeInstallPromptHandler);
  windowLike.addEventListener("appinstalled", appInstalledHandler);
}

export function subscribeInstallPrompt(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function subscribeAppInstalled(listener) {
  installedListeners.add(listener);
  return () => installedListeners.delete(listener);
}

export function getInstallPromptSnapshot() {
  return snapshot;
}

export async function promptForInstall() {
  const promptEvent = snapshot.deferredPrompt;
  if (!promptEvent || snapshot.installed || snapshot.prompting) {
    return { outcome: "unavailable" };
  }
  publish({ prompting: true, error: null });
  try {
    await promptEvent.prompt();
    const choice = await promptEvent.userChoice;
    const outcome = choice?.outcome === "accepted" ? "accepted" : "dismissed";
    publish({ deferredPrompt: null, lastOutcome: outcome, prompting: false });
    return choice || { outcome };
  } catch (error) {
    publish({ deferredPrompt: null, error, lastOutcome: "error", prompting: false });
    return { outcome: "error", error };
  }
}

export function resetInstallPromptCaptureForTests() {
  initializedWindow?.removeEventListener?.("beforeinstallprompt", beforeInstallPromptHandler);
  initializedWindow?.removeEventListener?.("appinstalled", appInstalledHandler);
  snapshot = {
    deferredPrompt: null,
    error: null,
    installed: false,
    lastOutcome: null,
    prompting: false,
  };
  initializedWindow = null;
  beforeInstallPromptHandler = null;
  appInstalledHandler = null;
  listeners.clear();
  installedListeners.clear();
}
