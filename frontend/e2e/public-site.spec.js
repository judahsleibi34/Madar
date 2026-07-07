import { expect, test } from "@playwright/test";

import { tenantSiteRoutes } from "./helpers/routes";
import { expectAppShell, expectNoFrontendCrash } from "./helpers/selectors";

test.describe("public tenant sites", () => {
  test("unknown public tenant site does not crash the frontend", async ({ page }) => {
    await page.goto(tenantSiteRoutes.unknownSite);
    await expectAppShell(page);
    await expectNoFrontendCrash(page);
    await expect(page.locator("body")).toBeVisible();
  });
});
