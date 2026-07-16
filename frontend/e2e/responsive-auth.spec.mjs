import { expect, test } from "@playwright/test";

const viewports = [
  [1920, 1080],
  [1680, 1050],
  [1600, 900],
  [1536, 864],
  [1440, 900],
  [1440, 810],
  [1366, 768],
  [1280, 800],
  [1280, 720],
  [1024, 768],
  [1024, 600],
  [768, 1024],
  [430, 932],
  [390, 844],
  [360, 800],
];

const routes = [
  "/",
  "/login",
  "/signup",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/demo",
  "/pricing",
  "/pricing/base-plans",
  "/pricing/custom-plan",
  "/team",
  "/about",
  "/contact",
  "/privacy-policy",
  "/terms-and-conditions",
  "/dashboard",
  "/admin/users",
  "/admin/account-access",
  "/notifications",
  "/page-builder/preview",
  "/page-builder/form-preview/responsive-audit",
  "/page-builder",
  "/builder-responses",
  "/builder-data",
  "/archive",
  "/my-plan",
  "/settings/change-password",
  "/settings/security",
  "/settings",
  "/site/responsive-audit",
];

async function inspectResponsiveLayout(page) {
  return page.evaluate(() => {
    const root = document.documentElement;
    const viewportWidth = root.clientWidth;
    const viewportHeight = window.innerHeight;
    const clippedFixedControls = [];

    for (const element of document.querySelectorAll("body *")) {
      const style = getComputedStyle(element);
      if (style.display === "none" || style.visibility === "hidden") continue;

      const rect = element.getBoundingClientRect();
      const isClosedDashboardDrawer =
        element.matches(".admin-sidebar") &&
        !document.querySelector(".admin-dashboard-layout.sidebar-open");

      if (
        !isClosedDashboardDrawer &&
        style.position === "fixed" &&
        (element.matches("button, a, input, select, textarea") ||
          element.querySelector("button, a, input, select, textarea")) &&
        (rect.bottom < 0 ||
          rect.top > viewportHeight ||
          rect.right < 0 ||
          rect.left > viewportWidth)
      ) {
        clippedFixedControls.push({
          tag: element.tagName.toLowerCase(),
          className: String(element.className || "").slice(0, 120),
        });
      }
    }

    return {
      hasHorizontalOverflow: root.scrollWidth > viewportWidth + 1,
      clientWidth: viewportWidth,
      scrollWidth: root.scrollWidth,
      clippedFixedControls,
    };
  });
}

async function logIn(page) {
  await page.goto("/login", { waitUntil: "domcontentloaded" });

  const emailInput = page.locator('input[name="email"]');
  const passwordInput = page.locator('input[name="password"]');
  await expect(emailInput).toBeVisible();
  await expect(passwordInput).toBeVisible();

  await emailInput.fill(process.env.TEST_USER_EMAIL);
  await passwordInput.fill(process.env.TEST_USER_PASSWORD);

  const loginResponsePromise = page.waitForResponse(
    (response) => response.url().includes("/auth/login") && response.request().method() === "POST"
  );
  await page.locator('button[type="submit"]').click();
  const loginResponse = await loginResponsePromise;

  // Never leave secrets in the DOM if authentication fails and Playwright
  // writes a diagnostic error context for the failed test.
  await emailInput.fill("").catch(() => {});
  await passwordInput.fill("").catch(() => {});

  if (!loginResponse.ok()) {
    throw new Error(`Dedicated test-account login failed with status ${loginResponse.status()}.`);
  }
  await page.waitForURL((url) => url.pathname.startsWith("/dashboard"), { timeout: 20_000 });
}

async function logOutAndNeutralize(page, issues) {
  try {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
    const logoutButton = page.locator(".admin-sidebar-logout");
    await logoutButton.waitFor({ state: "visible", timeout: 10_000 });
    await logoutButton.click();
    await page.waitForURL((url) => url.pathname === "/", { timeout: 20_000 });
  } catch {
    issues.push("The temporary authenticated browser session could not be logged out cleanly.");
  } finally {
    await page.context().clearCookies();
    await page.goto("/login", { waitUntil: "domcontentloaded" }).catch(() => {});
    await page
      .evaluate(() => {
        window.localStorage.clear();
        window.sessionStorage.clear();
      })
      .catch(() => {});
    await page.reload({ waitUntil: "domcontentloaded" }).catch(() => {});
    await page.locator('input[name="email"]').fill("").catch(() => {});
    await page.locator('input[name="password"]').fill("").catch(() => {});
  }
}

test("dedicated account: every route remains responsive while authenticated", async ({ page }) => {
  const pageErrors = [];
  const issues = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await logIn(page);

  try {
    for (const [width, height] of viewports) {
      await page.setViewportSize({ width, height });

      for (const route of routes) {
        pageErrors.length = 0;
        const response = await page.goto(route, {
          waitUntil: "domcontentloaded",
          timeout: 30_000,
        });
        await page.waitForTimeout(350);

        if ((response?.status() || 0) >= 400) {
          issues.push(`${route} did not return a successful document response at ${width}x${height}.`);
        }

        const layout = await inspectResponsiveLayout(page);
        if (layout.hasHorizontalOverflow) {
          issues.push(
            `${route} overflowed horizontally at ${width}x${height}: ${layout.scrollWidth}/${layout.clientWidth}.`
          );
        }
        if (layout.clippedFixedControls.length) {
          issues.push(`${route} had fixed controls outside the viewport at ${width}x${height}.`);
        }
        if (pageErrors.length) {
          issues.push(`${route} raised ${pageErrors.length} browser error(s) at ${width}x${height}.`);
        }
      }
    }
  } catch {
    issues.push("The authenticated responsive audit encountered an unexpected browser failure.");
  } finally {
    await logOutAndNeutralize(page, issues);
  }

  expect(issues, "Authenticated responsive audit failures.").toEqual([]);
});
