import { describe, expect, it } from "vitest";

import {
  getBrandedMadarSubdomain,
  getBrandedRuntimePath,
} from "./hostedAddress";

describe("hosted address routing", () => {
  it("recognizes a branded Madar hostname without changing standard paths", () => {
    expect(getBrandedMadarSubdomain("shop-name.madarportal.com")).toBe("shop-name");
    expect(getBrandedRuntimePath({
      hostname: "shop-name.madarportal.com",
      pathname: "/",
    })).toBe("/site/shop-name/");
    expect(getBrandedRuntimePath({
      hostname: "madarportal.com",
      pathname: "/site/shop-name/",
    })).toBe(
      ""
    );
  });

  it("rejects reserved, nested, invalid, and unrelated hostnames", () => {
    expect(getBrandedMadarSubdomain("www.madarportal.com")).toBe("");
    expect(getBrandedMadarSubdomain("a.b.madarportal.com")).toBe("");
    expect(getBrandedMadarSubdomain("-bad.madarportal.com")).toBe("");
    expect(getBrandedMadarSubdomain("example.com")).toBe("");
  });
});
