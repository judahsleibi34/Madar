import { test } from "@playwright/test";

import { publicRoutes } from "./helpers/routes";
import { expectAppShell, expectMeaningfulPageContent, expectNoFrontendCrash } from "./helpers/selectors";

const publicSmokePages = [
  publicRoutes.home,
  publicRoutes.productTour,
  publicRoutes.pricing,
  publicRoutes.pricingBasePlans,
  publicRoutes.team,
  publicRoutes.about,
  publicRoutes.contact,
  publicRoutes.demo,
];

test.describe("public pages", () => {
  for (const route of publicSmokePages) {
    test(`${route} loads without crashing`, async ({ page }) => {
      await page.goto(route);
      await expectAppShell(page);
      await expectNoFrontendCrash(page);
      await expectMeaningfulPageContent(page);
    });
  }
});
