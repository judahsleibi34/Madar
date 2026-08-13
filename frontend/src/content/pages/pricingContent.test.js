import { describe, expect, it } from "vitest";

import { pricingContent } from "./pricingContent";

describe("canonical pricing copy", () => {
  it("describes manual activation and the unlimited-volume fair-use policy", () => {
    expect(pricingContent.en.manualActivation.toLowerCase()).toContain("does not charge");
    expect(pricingContent.en.fairUse.toLowerCase()).toContain("not billed by count");
    expect(pricingContent.en.addressNote).toContain("$5/month");
  });

  it("does not contain WhatsApp pricing", () => {
    expect(JSON.stringify(pricingContent).toLowerCase()).not.toContain("whatsapp");
  });
});
