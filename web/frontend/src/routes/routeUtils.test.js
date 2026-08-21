import { describe, expect, it } from "vitest";

import { getSafePostLoginPath, isDashboardRoutePath, isTenantSiteRoutePath } from "./routeUtils";

describe("Ecommerce route classification", () => {
  it.each(["/store/palcode", "/store/palcode/catalog", "/shop", "/shop/categories"])(
    "treats %s as a public storefront route",
    (pathname) => {
      expect(isTenantSiteRoutePath(pathname)).toBe(true);
      expect(isDashboardRoutePath(pathname)).toBe(false);
    },
  );

  it.each([
    "/ecommerce/tags",
    "/ecommerce/categories",
    "/ecommerce/products",
    "/ecommerce/store",
  ])("treats %s as an authenticated dashboard route", (pathname) => {
    expect(isDashboardRoutePath(pathname)).toBe(true);
  });

  it("preserves an Ecommerce return path for a workspace user", () => {
    expect(
      getSafePostLoginPath(
        { user_type: "user" },
        "/ecommerce/products",
      ),
    ).toBe("/ecommerce/products");
  });
});

describe("Agenda route classification", () => {
  it("treats Agenda as an authenticated dashboard route", () => {
    expect(isDashboardRoutePath("/agenda")).toBe(true);
  });

  it("preserves an Agenda return path for a workspace user", () => {
    expect(
      getSafePostLoginPath(
        { user_type: "user" },
        "/agenda",
      ),
    ).toBe("/agenda");
  });
});
