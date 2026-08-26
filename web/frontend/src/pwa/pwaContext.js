import { getBrandedMadarSubdomain } from "../utils/hostedAddress";

export const MADAR_MANIFEST_PATH = "/manifest.webmanifest";
export const MADAR_THEME_COLOR = "#852c21";
export const MADAR_APPLE_TOUCH_ICON_PATH = "/madar-apple-touch-icon-180.png";

export function isIOSDevice(windowLike = globalThis.window) {
  const navigatorLike = windowLike?.navigator;
  const userAgent = navigatorLike?.userAgent || "";
  const platform = navigatorLike?.platform || "";

  return /iPad|iPhone|iPod/i.test(userAgent)
    || /iPad|iPhone|iPod/i.test(platform)
    || (platform === "MacIntel" && Number(navigatorLike?.maxTouchPoints || 0) > 1);
}

export function isAndroidDevice(windowLike = globalThis.window) {
  return /Android/i.test(windowLike?.navigator?.userAgent || "");
}

export function isMadarPwaHost(locationLike = globalThis.location) {
  return !getBrandedMadarSubdomain(locationLike?.hostname);
}

export function getMadarLaunchContext(windowLike = globalThis.window) {
  const mediaStandalone = Boolean(
    windowLike?.matchMedia?.("(display-mode: standalone)")?.matches
  );
  const isIOSStandalone = windowLike?.navigator?.standalone === true;
  const isStandalone = mediaStandalone || isIOSStandalone;

  return {
    displayMode: isStandalone ? "standalone" : "browser",
    isStandalone,
    isIOSStandalone,
  };
}

function ensureHeadElement(documentLike, selector, create) {
  const existing = documentLike.head?.querySelector(selector);
  if (existing) return existing;
  const element = create();
  documentLike.head?.append(element);
  return element;
}

export function installMadarPwaMetadata(documentLike = globalThis.document) {
  if (!documentLike?.head) return false;

  ensureHeadElement(documentLike, 'link[rel="manifest"]', () => {
    const link = documentLike.createElement("link");
    link.rel = "manifest";
    link.href = MADAR_MANIFEST_PATH;
    return link;
  });
  ensureHeadElement(documentLike, 'meta[name="theme-color"]', () => {
    const meta = documentLike.createElement("meta");
    meta.name = "theme-color";
    meta.content = MADAR_THEME_COLOR;
    return meta;
  });
  ensureHeadElement(documentLike, 'meta[name="apple-mobile-web-app-capable"]', () => {
    const meta = documentLike.createElement("meta");
    meta.name = "apple-mobile-web-app-capable";
    meta.content = "yes";
    return meta;
  });
  ensureHeadElement(documentLike, 'meta[name="mobile-web-app-capable"]', () => {
    const meta = documentLike.createElement("meta");
    meta.name = "mobile-web-app-capable";
    meta.content = "yes";
    return meta;
  });
  ensureHeadElement(documentLike, 'meta[name="apple-mobile-web-app-status-bar-style"]', () => {
    const meta = documentLike.createElement("meta");
    meta.name = "apple-mobile-web-app-status-bar-style";
    meta.content = "default";
    return meta;
  });
  ensureHeadElement(documentLike, 'meta[name="apple-mobile-web-app-title"]', () => {
    const meta = documentLike.createElement("meta");
    meta.name = "apple-mobile-web-app-title";
    meta.content = "Madar";
    return meta;
  });
  ensureHeadElement(documentLike, 'link[rel="apple-touch-icon"]', () => {
    const link = documentLike.createElement("link");
    link.rel = "apple-touch-icon";
    link.href = MADAR_APPLE_TOUCH_ICON_PATH;
    return link;
  });

  return true;
}
