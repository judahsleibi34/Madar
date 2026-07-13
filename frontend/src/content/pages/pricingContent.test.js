import { describe, expect, it } from "vitest";

import { pricingContent } from "./pricingContent";

describe("billing placeholder messaging", () => {
  it("describes plan selection as an access request with no charge", () => {
    expect(pricingContent.en.availabilityNotice.toLowerCase()).toContain("does not charge");
    expect(pricingContent.en.basePlans.every((plan) => plan.cta.startsWith("Request"))).toBe(true);
  });
});
