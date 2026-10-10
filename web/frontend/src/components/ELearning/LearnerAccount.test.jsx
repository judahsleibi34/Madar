import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import LearnerAccount from "./LearnerAccount";
import { fetchMyLearning, fetchReferralAccount } from "../../services/elearningPlayer";
import { apiFetch } from "../../utils/apiClient";
vi.mock("../../services/elearningPlayer", () => ({ fetchMyLearning: vi.fn(), fetchReferralAccount: vi.fn() }));
vi.mock("../../utils/apiClient", async original => ({ ...await original(), apiFetch: vi.fn() }));
const course = (id, completed, total, finished = false) => ({ course: { id, name: `Course ${id}` }, progress: { completed_lessons: completed, total_lessons: total, progress_percent: total ? Math.round(completed / total * 100) : 0, completion: { completed: finished } } });
const data = { courses: [course("one", 1, 2)], has_more: false, academy: { subdomain: "tenant" } };
const mount = () => render(<MemoryRouter><LearnerAccount /></MemoryRouter>);
beforeEach(async () => { fetchReferralAccount.mockResolvedValue({ available: false, enabled: false, balances: [], history: [] }); await i18n.changeLanguage("en"); apiFetch.mockResolvedValue({ ok: true, json: async () => ({ user: { first_name: "Maya", last_name: "Ali", email: "maya@example.com" } }) }); fetchMyLearning.mockResolvedValue(data); });
afterEach(() => { cleanup(); vi.resetAllMocks(); delete navigator.clipboard; });
it("uses all pages to calculate weighted progress and points, respecting formal course completion", async () => {
 fetchMyLearning.mockResolvedValueOnce({ ...data, has_more: true }).mockResolvedValueOnce({ courses: [course("two", 3, 3, true)], has_more: false });
 const { container } = mount(); await screen.findByRole("heading", { name: "Maya Ali" });
 expect(fetchMyLearning).toHaveBeenNthCalledWith(2, 1);
 expect([...container.querySelectorAll('.learner-account-stat strong')].map(node => node.textContent)).toEqual(["2", "1", "80%", "40"]);
 expect(screen.getByText("10 points per completed lesson")).toBeTruthy();
 expect(screen.getByRole("link", { name: "Open Course two" }).getAttribute("href")).toBe('/my-learning/courses/two');
});
it("copies a public invitation link without adding account data or granting access", async () => {
 const writeText = vi.fn().mockResolvedValue(); Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } });
 mount(); const field = await screen.findByLabelText("Invitation link");
 expect(field.value).toBe(new URL('/academy/tenant', window.location.origin).href);
 fireEvent.click(screen.getByRole("button", { name: "Copy invitation link" })); await screen.findByRole("button", { name: "Link copied" });
 expect(writeText).toHaveBeenCalledWith(field.value);
});
it("offers manual copying if clipboard permission is unavailable", async () => {
 Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: vi.fn().mockRejectedValue(new Error('Denied')) } });
 mount(); fireEvent.click(await screen.findByRole("button", { name: "Copy invitation link" }));
 await waitFor(() => expect(screen.getByRole("status").textContent).toContain("Select the link above"));
});
it("handles an empty account without an academy or profile", async () => {
 apiFetch.mockRejectedValue(new Error('Unavailable')); fetchMyLearning.mockResolvedValue({ courses: [], has_more: false });
 const { container } = mount(); await screen.findByRole("heading", { name: "Your learning profile" });
 expect([...container.querySelectorAll('.learner-account-stat strong')].map(node => node.textContent)).toEqual(["0", "0", "0%", "0"]);
 expect(screen.queryByRole("button", { name: "Copy invitation link" })).toBeNull();
 expect(screen.getByRole("link", { name: "Explore Courses" }).getAttribute("href")).toBe('/my-learning/catalog');
});
it("renders personalized referrals and keeps currencies and simulated balances separate", async () => {
 const code='11111111-1111-4111-8111-111111111111';
 fetchReferralAccount.mockResolvedValue({ available:true, enabled:true, code, reward_amount:'5.25', currency:'USD', referred_count:3, earned_count:2, balances:[{amount:'5.25',currency:'USD',simulated:false},{amount:'10.00',currency:'EUR',simulated:true}], history:[{id:'referral',amount:'5.25',currency:'USD',created_at:'2026-10-10T00:00:00Z',status:'pending',simulated:false}] });
 mount(); const field=await screen.findByLabelText('Invitation link');
 expect(new URL(field.value).searchParams.get('ref')).toBe(code);
 expect(screen.getByText('Earned reward balance')).toBeTruthy();expect(screen.getByText('Demo reward balance')).toBeTruthy();
 expect(screen.getByText('Awaiting first purchase')).toBeTruthy();expect(screen.getByText(/3 referred learners/)).toBeTruthy();
 expect(screen.queryByText(/Referral rewards and tracking are not enabled/)).toBeNull();
});
