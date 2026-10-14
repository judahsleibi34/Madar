import { describe, expect, it } from "vitest";

import { pricingContent } from "./pricingContent";

describe("canonical pricing copy", () => {
  it("describes strict paid continuity without recovery promises", () => {
    const english = JSON.stringify(pricingContent.en).toLowerCase();
    expect(english).toContain("continuous");
    expect(english).toContain("no grace period");
    expect(english).toContain("does not delete");
    expect(pricingContent.ar.title).toContain("أسعار");
  });

  it("does not contain WhatsApp pricing", () => {
    expect(JSON.stringify(pricingContent).toLowerCase()).not.toContain("whatsapp");
  });

  it("does not embed price amounts in translated presentation copy", () => {
    expect(JSON.stringify(pricingContent)).not.toMatch(/\$\s*(15|20|30|40)/);
  });
});
