import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import "../../i18n";
import AffiliateDashboard from "./AffiliateDashboard";
import { request } from "./academyProgrammeApi";
import { fetchReferralAccount } from "../../services/elearningPlayer";
vi.mock("./academyProgrammeApi", () => ({ request: vi.fn() }));
vi.mock("../../services/elearningPlayer", () => ({ fetchReferralAccount: vi.fn() }));
const account = status => ({ capabilities: { affiliate: true, withdrawal: true }, settings: { affiliates_enabled: true, withdrawals_enabled: true }, applications: status ? [{ id: "internal-id", kind: "affiliate", status, created_at: "2026-10-10", review_note: "Private" }] : [], withdrawals: [], wallet: { available: "17", currency: "USD" } });
beforeEach(() => { request.mockResolvedValue(account("approved")); fetchReferralAccount.mockResolvedValue({ available: true, balances: [{ currency: "USD", amount: "9", simulated: true }], history: [], referred_count: 2, earned_count: 1 }); });
afterEach(() => { cleanup(); vi.resetAllMocks(); });
const mount = () => render(<MemoryRouter><AffiliateDashboard /></MemoryRouter>);
it("supports an affiliate-only account through existing programme and referral reads", async () => {
  mount(); await screen.findByRole("heading", { name: "Affiliate dashboard" });
  expect(request).toHaveBeenCalledWith("/account");
  expect(screen.getByText(/Demo reward balance/)).toBeTruthy();
  expect(screen.getByRole("link", { name: "Referral link and activity" }).getAttribute("href")).toBe("/my-learning/referrals");
  expect(screen.queryByText("internal-id")).toBeNull(); expect(screen.queryByText("Private")).toBeNull();
});
it.each(["submitted", "under_review", "approved", "suspended"])("shows %s without offering a new application", async status => {
  request.mockResolvedValue(account(status)); mount(); await screen.findByRole("heading", { name: "Affiliate dashboard" });
  expect(screen.queryByRole("link", { name: "Become an affiliate" })).toBeNull();
  expect(screen.getByRole("link", { name: "Affiliate application" }).getAttribute("href")).toBe("/my-learning/affiliate/application");
});
it.each([undefined, "not_approved"])("allows a candidate without an open application to apply", async status => {
  request.mockResolvedValue(account(status)); mount();
  expect(await screen.findByRole("link", { name: "Become an affiliate" })).toBeTruthy();
});
it("fails closed when the tenant affiliate capability is absent", async () => {
  request.mockResolvedValue({ ...account("approved"), capabilities: { affiliate: false } }); mount();
  await screen.findByRole("alert"); expect(fetchReferralAccount).not.toHaveBeenCalled();
  expect(screen.queryByRole("link", { name: "Affiliate application" })).toBeNull();
});
