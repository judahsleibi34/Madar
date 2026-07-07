import { expect, test } from "@playwright/test";

import { e2eEnv, hasAdminCredentials, hasUserCredentials } from "./helpers/env";
import { loginWithUi } from "./helpers/auth";
import { dashboardRoutes, publicRoutes } from "./helpers/routes";
import { expectAppShell, expectNoFrontendCrash } from "./helpers/selectors";

test.describe("auth public pages", () => {
  test("login page loads", async ({ page }) => {
    await page.goto(publicRoutes.login);
    await expect(page.getByRole("heading", { name: /log in/i })).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
    await expect(page.getByLabel(/^password$/i)).toBeVisible();
  });

  test("signup page loads", async ({ page }) => {
    await page.goto(publicRoutes.signup);
    await expect(page.getByRole("heading", { name: /register/i })).toBeVisible();
    await expect(page.getByLabel(/first name/i)).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
  });

  test("forgot password page loads", async ({ page }) => {
    await page.goto(publicRoutes.forgotPassword);
    await expect(page.getByRole("heading", { name: /forgot password/i })).toBeVisible();
    await expect(page.getByLabel(/email/i)).toBeVisible();
  });
});

test.describe("authenticated user smoke", () => {
  test.skip(!hasUserCredentials(), "Set E2E_USER_EMAIL and E2E_USER_PASSWORD to run user login smoke tests.");

  test("user login and core workspace routes load", async ({ page }) => {
    await loginWithUi(page, {
      email: e2eEnv.userEmail,
      password: e2eEnv.userPassword,
    });

    for (const route of [
      dashboardRoutes.dashboard,
      dashboardRoutes.settings,
      dashboardRoutes.pageBuilder,
      dashboardRoutes.builderData,
    ]) {
      await page.goto(route);
      await expectAppShell(page);
      await expectNoFrontendCrash(page);
      await expect(page).not.toHaveURL(/\/login(?:\?|$)/);
    }
  });
});

test.describe("authenticated admin smoke", () => {
  test.skip(!hasAdminCredentials(), "Set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD to run admin smoke tests.");

  test("admin login and admin routes load", async ({ page }) => {
    await loginWithUi(page, {
      email: e2eEnv.adminEmail,
      password: e2eEnv.adminPassword,
    });

    for (const route of [
      dashboardRoutes.dashboard,
      dashboardRoutes.adminUsers,
      dashboardRoutes.adminAccountAccess,
    ]) {
      await page.goto(route);
      await expectAppShell(page);
      await expectNoFrontendCrash(page);
      await expect(page).not.toHaveURL(/\/login(?:\?|$)/);
    }
  });
});
