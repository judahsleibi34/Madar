import { describe, expect, it } from "vitest";

import { getSafePostLoginPath, isDashboardRoutePath, isTenantSiteRoutePath } from "./routeUtils";

describe("Ecommerce route classification", () => {
  it.each(["/shop", "/shop/categories"])(
    "treats %s as a canonical storefront route",
    (pathname) => {
      expect(isTenantSiteRoutePath(pathname)).toBe(true);
      expect(isDashboardRoutePath(pathname)).toBe(false);
    },
  );

  it.each(["/store/palcode", "/store/palcode/catalog", "/site/palcode/shop/product/chair"])(
    "routes legacy input %s through tenant compatibility handling",
    (pathname) => expect(isTenantSiteRoutePath(pathname)).toBe(true),
  );

  it("routes internal draft previews separately from public storefronts", () => {
    expect(isTenantSiteRoutePath("/ecommerce-preview/palcode/catalog")).toBe(true);
  });

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


describe("Platform commercial route", () => {
  it("uses the dashboard shell and rejects tenant post-login context", () => {
    expect(isDashboardRoutePath("/admin/tenants/42/commercial")).toBe(true);
    expect(getSafePostLoginPath({ user_type: "admin" }, "/admin/tenants/42/commercial")).toBe("/admin/tenants/42/commercial");
    expect(getSafePostLoginPath({ user_type: "user" }, "/admin/tenants/42/commercial")).not.toBe("/admin/tenants/42/commercial");
  });
});

it("classifies E-Learning settings as an authenticated dashboard route", () => {
  expect(isDashboardRoutePath("/e-learning/settings")).toBe(true);
});

it("keeps learner pages in the dashboard shell", () => { expect(isDashboardRoutePath("/my-learning/courses/c/lessons/l")).toBe(true); });
