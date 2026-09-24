import { describe, expect, it } from "vitest";

import {
  getBrandedMadarSubdomain,
  getBrandedRuntimePath,
  buildCanonicalTenantUrl,
} from "./hostedAddress";

describe("hosted address routing", () => {
  it("recognizes a branded Madar hostname without changing standard paths", () => {
    expect(getBrandedMadarSubdomain("shop-name.madarportal.com")).toBe("shop-name");
    expect(getBrandedRuntimePath({
      hostname: "shop-name.madarportal.com",
      pathname: "/",
    })).toBe("");
    expect(getBrandedRuntimePath({
      hostname: "shop-name.madarportal.com",
      pathname: "/shop/products",
    })).toBe("");
    expect(getBrandedRuntimePath({
      hostname: "madarportal.com",
      pathname: "/site/shop-name/",
    })).toBe(
      ""
    );
    expect(buildCanonicalTenantUrl("shop-name", "/about")).toBe(
      "https://shop-name.madarportal.com/about"
    );
  });

  it("rejects reserved, nested, invalid, and unrelated hostnames", () => {
    expect(getBrandedMadarSubdomain("www.madarportal.com")).toBe("");
    expect(getBrandedMadarSubdomain("a.b.madarportal.com")).toBe("");
    expect(getBrandedMadarSubdomain("-bad.madarportal.com")).toBe("");
    expect(getBrandedMadarSubdomain("example.com")).toBe("");
    expect(getBrandedMadarSubdomain("ACME.madarportal.com")).toBe("acme");
    expect(getBrandedMadarSubdomain("acme.madarportal.com.")).toBe("acme");
    expect(getBrandedMadarSubdomain("api.madarportal.com")).toBe("");
    expect(getBrandedMadarSubdomain("evil-madarportal.com")).toBe("");
    expect(getBrandedMadarSubdomain("acme.madarportal.com.evil.com")).toBe("");
    expect(getBrandedMadarSubdomain("invalid..madarportal.com")).toBe("");
    expect(getBrandedMadarSubdomain("invalid-.madarportal.com")).toBe("");
  });
});
