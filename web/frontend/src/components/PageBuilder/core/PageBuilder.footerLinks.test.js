import { describe, expect, it } from "vitest";

import {
  getFooterLinkItems,
  getSafeFooterLinkUrl,
  isExternalFooterLink,
} from "./PageBuilder.footerLinks";

describe("footer destination links", () => {
  it("keeps legacy label-only values compatible", () => {
    expect(getFooterLinkItems([], "Instagram\nVisa")).toEqual([
      { label: "Instagram", url: "" },
      { label: "Visa", url: "" },
    ]);
  });

  it("accepts HTTPS and internal endpoints but blocks unsafe schemes", () => {
    expect(getSafeFooterLinkUrl("https://instagram.com/madar", "Instagram")).toBe("https://instagram.com/madar");
    expect(getSafeFooterLinkUrl("/checkout", "Pay")).toBe("/checkout");
    expect(getSafeFooterLinkUrl("javascript:alert(1)", "Unsafe")).toBe("");
    expect(isExternalFooterLink("https://example.com")).toBe(true);
    expect(isExternalFooterLink("/checkout")).toBe(false);
  });
});
