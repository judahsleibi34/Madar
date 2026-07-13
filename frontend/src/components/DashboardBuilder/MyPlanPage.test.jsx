import { describe, expect, it } from "vitest";
import { getBillingDisplayState } from "./MyPlanPage";

describe("My Plan persisted billing state", () => {
  it("shows an active entitlement without hiding a separate pending request", () => {
    const active = { id: 1, plan: "pro", payment_status: "active" };
    const pending = { id: 2, plan: "complete", payment_status: "pending" };
    expect(getBillingDisplayState({ active, pending_request: pending })).toEqual({
      active,
      pending,
      current: active,
      state: "active",
      cards: [
        { kind: "active", feature: active },
        { kind: "pending", feature: pending },
      ],
    });
  });

  it("renders a pending-only request exactly once", () => {
    const pending = { id: 2, subscription_type: "full_platform", plan: "complete", payment_status: "pending" };
    expect(getBillingDisplayState({ current: pending, pending_request: pending }).cards).toEqual([
      { kind: "pending", feature: pending },
    ]);
  });

  it("does not duplicate an identical pending state beside an active plan", () => {
    const active = { id: 1, subscription_type: "full_platform", plan: "complete", payment_status: "active" };
    const pending = { id: 2, subscription_type: "full_platform", plan: "complete", payment_status: "pending" };
    const view = getBillingDisplayState({ active, current: active, pending_request: pending });
    expect(view.pending).toBeNull();
    expect(view.cards).toEqual([{ kind: "active", feature: active }]);
  });

  it("is stable across repeated normalization", () => {
    const pending = { id: 9, subscription_type: "full_platform", plan: "complete", payment_status: "pending" };
    const first = getBillingDisplayState({ current: pending, pending_request: pending });
    const second = getBillingDisplayState({ current: pending, pending_request: pending });
    expect(second.cards).toEqual(first.cards);
  });

  it("represents an empty tenant without placeholder plan data", () => {
    expect(getBillingDisplayState({ state: "none" })).toEqual({
      active: null,
      pending: null,
      current: null,
      state: "none",
      cards: [],
    });
  });
});
