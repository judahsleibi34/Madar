import { describe, expect, it } from "vitest";
import { pendingRewards, referralState, referralView, shareTargets, tuitionProgress, walletHistory, withdrawState } from "./studentFinance";

describe("referralView", () => {
  it("shows a link only when the backend issued a code", () => {
    expect(referralView({ available: true, enabled: true, code: "ABC123" })).toBe("link");
    expect(referralView({ available: true, enabled: true, code: null })).toBe("invite");
    expect(referralView({ available: true, enabled: false, code: "ABC123" })).toBe("invite");
    expect(referralView({ available: false })).toBe("unavailable");
    expect(referralView(null)).toBe("unavailable");
  });
});

describe("tuitionProgress", () => {
  it("counts sales towards the threshold and trusts the backend's eligibility", () => {
    expect(tuitionProgress({ verified_sales: 2, threshold: 4, tuition_eligible: false })).toEqual({ sales: 2, threshold: 4, remaining: 2, eligible: false });
    expect(tuitionProgress({ verified_sales: 4, threshold: 4, tuition_eligible: true })).toMatchObject({ remaining: 0, eligible: true });
    expect(tuitionProgress({ verified_sales: 5, threshold: 4, tuition_eligible: false }).eligible).toBe(false);
    expect(tuitionProgress(null)).toMatchObject({ sales: 0, threshold: 4, remaining: 4, eligible: false });
  });
});

describe("wallet", () => {
  const referrals = { referred_count: 5, history: [
    { id: "r1", amount: "10", currency: "USD", status: "earned", created_at: "2026-01-01", earned_at: "2026-01-02" },
    { id: "r2", amount: "10", currency: "USD", status: "pending", created_at: "2026-01-03" },
    { id: "r3", amount: "10", currency: "USD", status: "reversed", created_at: "2026-01-01", reversed_at: "2026-01-04" },
    { id: "r4", amount: "10", currency: "USD", status: "earned", created_at: "2026-01-01", earned_at: "2026-01-05", simulated: true },
    { id: "r5", amount: "10", currency: "USD", status: "pending", reward_status: "pending", created_at: "2026-01-06" },
  ] };
  it("never treats a sign-up without a purchase as money", () => {
    expect(referralState({ status: "pending" })).toEqual({ signup: true, reward: null });
    expect(referralState({ status: "earned" })).toEqual({ signup: false, reward: "available" });
    expect(referralState({ status: "rejected", reward_status: "rejected" })).toEqual({ signup: false, reward: "rejected" });
    expect(pendingRewards(referrals)).toBe(10);
    expect(pendingRewards({ history: [{ status: "pending", amount: 10 }] })).toBe(0);
  });
  it("lists rewards and withdrawals newest first with the available balance after each", () => {
    const rows = walletHistory(referrals, [{ id: "w1", amount: "5", currency: "USD", status: "paid", created_at: "2026-01-07" }, { id: "w2", amount: "3", currency: "USD", status: "rejected", created_at: "2026-01-08" }]);
    expect(rows.map(row => [row.id, row.status, row.amount, row.balanceAfter])).toEqual([
      ["withdrawal:w2", "rejected", -3, 5],
      ["withdrawal:w1", "paid", -5, 5],
      ["reward:r5", "pending", 10, 10],
      ["reward:r4", "available", 10, 10],
      ["reward:r3", "reversed", 10, 10],
      ["reward:r1", "available", 10, 10],
    ]);
  });
  it("leaves the running balance out when the history is incomplete", () => {
    expect(walletHistory({ referred_count: 60, history: referrals.history }).every(row => row.balanceAfter === null)).toBe(true);
  });
});

describe("withdrawState", () => {
  const settings = { withdrawals_enabled: true, minimum_withdrawal_amount: "50", withdrawal_methods: ["PayPal"] };
  it("allows only Available Balance at or above the admin minimum", () => {
    expect(withdrawState({ available: "20" }, settings).state).toBe("belowMinimum");
    expect(withdrawState({ available: "50" }, settings).state).toBe("eligible");
    expect(withdrawState({ available: "80", debt: "5" }, settings).state).toBe("blocked");
    expect(withdrawState({ available: "80" }, { ...settings, withdrawals_enabled: false }).state).toBe("unavailable");
    expect(withdrawState({ available: "80" }, { ...settings, withdrawal_methods: [] }).state).toBe("unavailable");
  });
});

it("builds share targets for every document channel", () => {
  const targets = shareTargets("https://x.test/academy?ref=A", "Learn");
  expect(targets.map(([key]) => key)).toEqual(["whatsapp", "facebook", "instagram", "telegram", "email"]);
  expect(targets[0][2]).toContain(encodeURIComponent("https://x.test/academy?ref=A"));
  expect(targets[2][2]).toBeNull();
});
