import { describe, expect, it } from "vitest";
import { buildMyPlanView } from "./MyPlanPage";

describe("My Plan authoritative view", () => {
  it("uses catalog and backend entitlement data without static billing values", () => {
    const view = buildMyPlanView({
      catalog: {
        products: [{ id: "business", name: "Business", price_minor: 2500 }],
      },
      currentPlan: { plan_id: "business", state: "active", source: "canonical" },
      usage: {
        storage: { used_bytes: 10, quota_bytes: 20 },
        workspace_seats: { used: 1, included_and_added: 1 },
        ai_tokens: { remaining_standard_tokens: 0 },
      },
      entitlements: {
        capabilities: ["standard_hosted_address"],
      },
      addons: {
        active: [],
        available: [{ id: "ocr", coming_soon: true }],
      },
    });

    expect(view.planProduct).toEqual(
      expect.objectContaining({ id: "business", price_minor: 2500 })
    );
    expect(view.standardAddress).toBe(true);
    expect(view.brandedSubdomain).toBe(false);
    expect(view.futureAddons.map((item) => item.id)).toEqual(["ocr"]);
  });
});
