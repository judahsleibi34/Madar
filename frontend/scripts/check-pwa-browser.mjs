import { chromium } from "playwright";

const appUrl = String(process.argv[2] || "").replace(/\/$/, "");
const publicSiteUrl = String(process.argv[3] || "").replace(/\/$/, "");

if (!/^http:\/\/(?:127\.0\.0\.1|localhost)(?::\d+)?$/.test(appUrl)) {
  throw new Error("PWA browser audit requires an explicit loopback app URL");
}

const browser = await chromium.launch({
  headless: true,
  ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
    ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH }
    : {}),
  args: ["--host-resolver-rules=MAP customer.madarportal.com 127.0.0.1"],
});

try {
  const context = await browser.newContext();
  await context.addInitScript(() => {
    globalThis.__madarPermissionRequests = 0;
    if (globalThis.Notification?.requestPermission) {
      Notification.requestPermission = async () => {
        globalThis.__madarPermissionRequests += 1;
        return "denied";
      };
    }
  });
  const page = await context.newPage();
  await page.goto(appUrl, { waitUntil: "domcontentloaded" });

  const manifestHref = await page.locator('link[rel="manifest"]').getAttribute("href");
  if (manifestHref !== "/manifest.webmanifest") {
    throw new Error(`manifest link mismatch: ${manifestHref}`);
  }
  const registration = await page.evaluate(async () => {
    const ready = await navigator.serviceWorker.ready;
    return {
      permissionRequests: globalThis.__madarPermissionRequests,
      scope: ready.scope,
      scriptURL: ready.active?.scriptURL || "",
      cacheNames: await caches.keys(),
    };
  });
  if (!registration.scope.endsWith("/")) throw new Error("service worker scope is not root");
  if (!registration.scriptURL.endsWith("/madar-push-sw.js")) {
    throw new Error("unexpected service worker script URL");
  }
  if (registration.permissionRequests !== 0) {
    throw new Error("service-worker bootstrap requested notification permission");
  }
  if (registration.cacheNames.length !== 0) {
    throw new Error("Phase 3 service worker unexpectedly created caches");
  }
  const devtools = await context.newCDPSession(page);
  const appManifest = await devtools.send("Page.getAppManifest");
  if (!appManifest.url.endsWith("/manifest.webmanifest") || appManifest.errors.length) {
    throw new Error(
      `browser rejected the app manifest: ${JSON.stringify(appManifest.errors)}`
    );
  }
  const manifestData = JSON.parse(appManifest.data);
  if (manifestData.start_url !== "/dashboard" || manifestData.scope !== "/") {
    throw new Error("browser observed an unexpected PWA start URL or scope");
  }
  const installability = await devtools.send("Page.getInstallabilityErrors");
  if (installability.installabilityErrors.length) {
    throw new Error(
      `browser reported installability errors: ${JSON.stringify(installability.installabilityErrors)}`
    );
  }

  if (publicSiteUrl) {
    const publicContext = await browser.newContext();
    const publicPage = await publicContext.newPage();
    await publicPage.goto(publicSiteUrl, { waitUntil: "domcontentloaded" });
    const publicState = await publicPage.evaluate(async () => ({
      manifestLinked: Boolean(document.querySelector('link[rel="manifest"]')),
      registration: Boolean(
        await navigator.serviceWorker?.getRegistration?.("/")
      ),
    }));
    await publicContext.close();
    if (publicState.manifestLinked || publicState.registration) {
      throw new Error("branded public site inherited the Madar PWA bootstrap");
    }
  }

  await context.close();
  console.log("Madar PWA browser smoke passed.");
} finally {
  await browser.close();
}
