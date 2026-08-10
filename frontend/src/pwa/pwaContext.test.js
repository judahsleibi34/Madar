import { beforeEach, describe, expect, it } from "vitest";

import {
  getMadarLaunchContext,
  installMadarPwaMetadata,
  isMadarPwaHost,
  MADAR_MANIFEST_PATH,
} from "./pwaContext";

describe("Madar PWA launch context", () => {
  beforeEach(() => {
    document.head
      .querySelectorAll('link[rel="manifest"], link[rel="apple-touch-icon"], meta[name^="apple-mobile-web-app"], meta[name="theme-color"]')
      .forEach((element) => element.remove());
  });

  it("detects display-mode standalone", () => {
    const context = getMadarLaunchContext({
      matchMedia: () => ({ matches: true }),
      navigator: {},
    });
    expect(context).toEqual({
      displayMode: "standalone",
      isStandalone: true,
      isIOSStandalone: false,
    });
  });

  it("detects iOS home-screen standalone", () => {
    const context = getMadarLaunchContext({
      matchMedia: () => ({ matches: false }),
      navigator: { standalone: true },
    });
    expect(context.isStandalone).toBe(true);
    expect(context.isIOSStandalone).toBe(true);
  });

  it("defaults safely to a normal browser", () => {
    expect(getMadarLaunchContext({ navigator: {} })).toEqual({
      displayMode: "browser",
      isStandalone: false,
      isIOSStandalone: false,
    });
  });

  it("keeps branded public-site hosts outside the Madar PWA", () => {
    expect(isMadarPwaHost({ hostname: "customer.madarportal.com" })).toBe(false);
    expect(isMadarPwaHost({ hostname: "app.madarportal.com" })).toBe(true);
    expect(isMadarPwaHost({ hostname: "localhost" })).toBe(true);
  });

  it("installs one set of application-host metadata", () => {
    expect(installMadarPwaMetadata(document)).toBe(true);
    expect(installMadarPwaMetadata(document)).toBe(true);
    expect(document.querySelectorAll('link[rel="manifest"]')).toHaveLength(1);
    expect(document.querySelector('link[rel="manifest"]').getAttribute("href")).toBe(
      MADAR_MANIFEST_PATH
    );
    expect(document.querySelector('meta[name="apple-mobile-web-app-capable"]').content).toBe(
      "yes"
    );
  });
});
