import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../../i18n";
import ELearningPlayer from "../ELearningPlayer";
import * as api from "../../../services/elearningPlayer";
import * as programmes from "../academyProgrammeApi";

vi.mock("../../../services/elearningPlayer", () => ({ fetchReferralAccount: vi.fn(), fetchMyLearning: vi.fn(), fetchLearningCourse: vi.fn(), fetchLearningLesson: vi.fn(), completeLearningLesson: vi.fn(), fetchLearningAccountContext: vi.fn() }));
vi.mock("../academyProgrammeApi", () => ({ request: vi.fn() }));
vi.mock("../../../services/elearningCredentials", () => ({ fetchCertificates: vi.fn(() => Promise.resolve({ credentials: [] })) }));

const academy = (extra = {}) => ({ subdomain: "aooloo", brand: "EduHope", experience: { studentDashboard: true }, ...extra });
const level = (index, lessons) => ({ id: `s${index}`, name: `Level ${index} — Title ${index}`, progress_percent: 0, lessons });
const enrolled = { course: { id: "c", name: "EduHope English Conversation Course" }, progress: { progress_percent: 10, completed_lessons: 1, total_lessons: 10, progress_status: "active" } };
const account = (extra = {}) => ({ capabilities: { affiliate: true, tuition: true, exchange: true, withdrawal: true, wallet: true }, settings: { affiliates_enabled: true, tuition_support_enabled: true, exchange_programme_enabled: true, withdrawals_enabled: true, minimum_withdrawal_amount: "50", withdrawal_methods: ["PayPal"] },
  wallet: { currency: "USD", available: "20", pending: "0", total_earned: "20", total_withdrawn: "0", debt: "0", verified_sales: 2, threshold: 4, remaining_sales: 2, tuition_eligible: false }, applications: [], withdrawals: [], ...extra });

function setup({ site = academy(), courses = [enrolled], referrals, programme = account() } = {}) {
  api.fetchMyLearning.mockResolvedValue({ courses, academy: site, settings: {}, has_more: false });
  api.fetchLearningAccountContext.mockResolvedValue({ academy: site, settings: {} });
  api.fetchLearningCourse.mockResolvedValue({ ...enrolled, sections: [level(1, [{ id: "t1", name: "Greetings", completed: true }, { id: "t2", name: "Introductions", completed: false }]), level(2, [{ id: "t3", name: "Family", locked: true }])], continue_lesson_id: "t2", assessments: [] });
  api.fetchReferralAccount.mockResolvedValue(referrals);
  programmes.request.mockResolvedValue(programme);
}
const page = path => render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/my-learning/*" element={<ELearningPlayer />} /></Routes></MemoryRouter>);

beforeEach(async () => { await i18n.changeLanguage("en"); });
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it("never shows a referral link to a member who has not purchased", async () => {
  setup({ courses: [], referrals: { available: true, enabled: true, code: null, history: [], balances: [] } });
  const { container } = page("/my-learning/referral");
  await screen.findByText("You haven't purchased the course yet. If you would like to promote EduHope without purchasing the course, you can apply to become an Affiliate.");
  expect(screen.getByRole("link", { name: "Become an Affiliate" })).toBeTruthy();
  expect(container.innerHTML).not.toMatch(/[?&;]ref=/);
  expect(container.querySelector("input")).toBeNull();
  expect(screen.queryByRole("button", { name: "Copy Link" })).toBeNull();
});

it("shows an approved affiliate their referral link and sharing buttons", async () => {
  setup({ courses: [], referrals: { available: true, enabled: true, code: "ABC123", reward_amount: "10", currency: "USD", history: [], balances: [], referred_count: 0 },
    programme: account({ applications: [{ id: "a", kind: "affiliate", status: "approved", created_at: "2026-01-01" }] }) });
  page("/my-learning/referral");
  const input = await screen.findByLabelText("Your referral link");
  expect(input.value).toContain("ref=ABC123");
  expect(screen.getByRole("link", { name: "WhatsApp" }).getAttribute("href")).toContain(encodeURIComponent("ref=ABC123"));
  expect(screen.getByText("Successful Sales: 2 / 4")).toBeTruthy();
  expect(screen.getByText(/Remaining Sales: 2/)).toBeTruthy();
});

it("keeps Withdraw disabled below the admin minimum with the document message", async () => {
  setup({ referrals: { available: true, enabled: true, code: "ABC123", history: [], balances: [] } });
  page("/my-learning/withdraw");
  await screen.findByText("Your available balance has not reached the minimum withdrawal amount yet.");
  expect(screen.getByRole("button", { name: "Request Withdrawal" }).disabled).toBe(true);
});

it("locks Tuition Support until the required sales and keeps Exchange open", async () => {
  setup({ referrals: { available: true, enabled: true, code: "ABC123", history: [], balances: [] } });
  page("/my-learning/applications");
  await screen.findByText("Tuition Support Locked");
  expect(screen.getByRole("button", { name: "Apply Now" }).disabled).toBe(true);
  expect(screen.getByText("Completing Level 4 is not a Tuition Support eligibility requirement.")).toBeTruthy();
  expect(screen.getByRole("link", { name: "Apply" })).toBeTruthy();
});

it("shows the 10-Level path with CEFR badges and icon + text states", async () => {
  setup({ referrals: { available: true, enabled: true, code: "ABC123", history: [], balances: [] } });
  page("/my-learning/course");
  await screen.findByText("Level 1 of 2");
  expect(screen.getAllByText("A1")).toHaveLength(2);
  expect(screen.getByText("In Progress · 0%")).toBeTruthy();
  expect(screen.getByText("Locked")).toBeTruthy();
  expect(document.body.textContent.toLowerCase()).not.toContain("milestone");
});

it("greets PAU members in Arabic, right to left", async () => {
  await i18n.changeLanguage("ar");
  setup({ site: academy({ institution: { member: true, name: "Palestine Ahliya University", label: "PAU Student" } }), referrals: { available: true, enabled: true, code: null, history: [], balances: [] } });
  const { container } = page("/my-learning/dashboard");
  await screen.findByText("مرحبًا بك يا طالب جامعة فلسطين الأهلية! 🎓");
  expect(container.querySelector(".elearning-player").getAttribute("dir")).toBe("rtl");
  expect(screen.getAllByText("PAU Student").length).toBeGreaterThan(0);
});

it("leaves every other academy on the existing learner screens", async () => {
  setup({ site: { subdomain: "other", brand: "Other" }, referrals: { available: true, enabled: true, code: "XYZ", history: [], balances: [] } });
  const { container } = page("/my-learning/referral");
  await waitFor(() => expect(container.querySelector("#learning-navigation nav")).toBeTruthy());
  const nav = container.querySelector("#learning-navigation nav");
  expect(nav.textContent).not.toContain("My Referral");
  expect(nav.textContent).not.toContain("Withdraw");
  expect(screen.queryByText("Become an Affiliate")).toBeNull();
  expect(screen.queryByLabelText("Your referral link")).toBeNull();
});

const affiliateReferrals = { available: true, enabled: true, code: "AFF123", clicks: 37, reward_amount: "10", currency: "USD", history: [{ id: "r1", amount: "10", currency: "USD", status: "pending", created_at: "2026-10-01" }], balances: [], referred_count: 1 };
const asAffiliate = (status, referrals = affiliateReferrals) => setup({ courses: [], referrals, programme: account({ applications: [{ id: "a", kind: "affiliate", status, created_at: "2026-01-01" }] }) });

it("gives approved affiliates their own dashboard without course or Tuition Support", async () => {
  asAffiliate("approved");
  const { container } = page("/my-learning/dashboard");
  await screen.findByText("Total Clicks");
  expect(screen.getByText("37")).toBeTruthy();
  const nav = container.querySelector("#learning-navigation nav").textContent;
  for (const label of ["Referral Link", "Clicks", "Sales", "Rewards", "Wallet", "Withdraw", "Transactions", "Notifications", "Profile"]) expect(nav).toContain(label);
  expect(nav).not.toContain("My Course");
  expect(nav).not.toContain("Applications");
  expect(document.body.textContent).not.toContain("Tuition Support");
});

it("shows the affiliate referral link with sharing buttons", async () => {
  asAffiliate("approved");
  page("/my-learning/affiliate/link");
  expect((await screen.findByLabelText("Your referral link")).value).toContain("ref=AFF123");
  for (const name of ["WhatsApp", "Facebook", "Email"]) expect(screen.getByRole("link", { name })).toBeTruthy();
  expect(screen.getByRole("button", { name: "Instagram" })).toBeTruthy();
});

it("keeps the link hidden while an affiliate is under review or suspended", async () => {
  for (const [status, label] of [["under_review", "Under Review"], ["suspended", "Suspended"]]) {
    asAffiliate(status, { ...affiliateReferrals, code: status === "suspended" ? "AFF123" : null });
    const { container } = page("/my-learning/affiliate/link");
    await screen.findByText(label);
    expect(container.querySelector("input")).toBeNull();
    expect(container.innerHTML).not.toMatch(/[?&;]ref=/);
    cleanup(); vi.resetAllMocks();
  }
});

it("keeps every other academy on the existing affiliate dashboard", async () => {
  setup({ site: { subdomain: "other", brand: "Other" }, courses: [], referrals: affiliateReferrals, programme: account({ applications: [{ id: "a", kind: "affiliate", status: "approved", created_at: "2026-01-01" }] }) });
  const { container } = page("/my-learning/affiliate");
  await waitFor(() => expect(container.querySelector(".affiliate-dashboard")).toBeTruthy());
  expect(screen.queryByText("Total Clicks")).toBeNull();
});
