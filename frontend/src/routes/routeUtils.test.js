import { describe, expect, it } from "vitest";

import { getSafePostLoginPath, isDashboardRoutePath } from "./routeUtils";

describe("Ecommerce route classification", () => {
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
