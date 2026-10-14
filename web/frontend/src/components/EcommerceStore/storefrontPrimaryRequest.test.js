import { describe, expect, it } from "vitest";

import { getStorefrontPrimaryRequest, parseStorefrontRoute } from "./storefrontPrimaryRequest";

describe("storefront primary request", () => {
  it.each([
    ["", { type: "catalog" }],
    ["catalog", { type: "catalog" }],
    ["categories", { type: "catalog" }],
    ["product/linen-shirt", { type: "product", slug: "linen-shirt", locale: "en" }],
    ["catalog/product/linen-shirt/", { type: "product", slug: "linen-shirt", locale: "en" }],
    ["contact", { type: "profile" }],
    ["checkout/", { type: "profile" }],
    [`confirmation/${"f".repeat(64)}`, { type: "confirmation", token: "f".repeat(64) }],
  ])("selects the read for route tail %j", (routeTail, expected) => {
    expect(getStorefrontPrimaryRequest({ routeTail })).toMatchObject(expected);
  });

  it("builds catalog filters in the storefront's request order and defaults", () => {
    const request = getStorefrontPrimaryRequest({ routeTail: "catalog", search: "?max_price=90&tag=new&search=tee", locale: "ar" });
    expect(request).toEqual({
      type: "catalog",
      filters: {
        search: "tee",
        category: "",
        brand: "",
        tag: "new",
        min_price: "",
        max_price: "90",
        sort: "latest",
        page: "1",
        locale: "ar",
        limit: "12",
      },
    });
  });

  it("parses the same route flags the storefront renders from", () => {
    expect(parseStorefrontRoute("contact")).toEqual({ productSlug: "", contactRoute: true, checkoutRoute: false, confirmationToken: "" });
    expect(parseStorefrontRoute("confirmation/not-a-token")).toMatchObject({ confirmationToken: "" });
  });
});
