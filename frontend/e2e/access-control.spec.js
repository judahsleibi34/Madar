import { test } from "@playwright/test";

import { dashboardRoutes } from "./helpers/routes";
import { expectLoginRoute } from "./helpers/selectors";

const protectedRoutes = [
  ["dashboard", dashboardRoutes.dashboard],
  ["page builder", dashboardRoutes.pageBuilder],
  ["data workspace", dashboardRoutes.builderData],
  ["admin users", dashboardRoutes.adminUsers],
  ["admin account access", dashboardRoutes.adminAccountAccess],
];

test.describe("unauthenticated access control", () => {
  for (const [name, route] of protectedRoutes) {
    test(`${name} redirects to login`, async ({ page }) => {
      await page.context().clearCookies();
      await page.goto(route);
      await expectLoginRoute(page);
    });
  }
});
