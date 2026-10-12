import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AcademyProgrammesPage from "./AcademyProgrammesPage";
import { apiFetch } from "../../utils/apiClient";
vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: key => key, i18n: { dir: () => "rtl", language: "ar" } }) }));
vi.mock("../../utils/apiClient", () => ({ getApiUrl: value => value, apiFetch: vi.fn() }));
const data = () => ({ wallet: { available: "40.00", pending: "0", debt: "0", total_earned: "40", total_withdrawn: "0", currency: "USD", verified_sales: 3, threshold: 4, remaining_sales: 1, tuition_eligible: false, exchange_eligible: true }, settings: { affiliates_enabled: true, tuition_support_enabled: true, exchange_programme_enabled: true, withdrawals_enabled: true, support_programme_name: "elearning.programmes.tuition", minimum_withdrawal_amount: "50.00", withdrawal_methods: ["PayPal"] }, applications: [], withdrawals: [] });
beforeEach(() => { apiFetch.mockReset();apiFetch.mockResolvedValue({ ok: true, json: async () => data() }); });
afterEach(cleanup);
const mount = props => render(<MemoryRouter><AcademyProgrammesPage {...props} /></MemoryRouter>);
it("hides unconfigured learner actions and never renders private review notes", async () => {
 apiFetch.mockResolvedValue({ok:true,json:async()=>({...data(),settings:{},applications:[{id:"a",kind:"affiliate",status:"submitted",created_at:"2026-10-10",details:{full_name:"Learner"},review_note:"Private owner review"}]})});
 mount();await screen.findByRole("heading",{name:"Learner"});
 expect(screen.queryByRole("button",{name:"elearning.programmes.submit"})).toBeNull();
 expect(screen.queryByText("Private owner review")).toBeNull();
 expect(screen.getByRole("table",{hidden:true})).toBeTruthy();
});
it("locks support below the server threshold and withdrawals below available funds", async () => {
  mount();await screen.findByRole("button", {name:"elearning.programmes.affiliate"});
  fireEvent.click(screen.getByRole("button", { name: "elearning.programmes.tuition" }));
  expect(screen.getByRole("button", { name: "elearning.programmes.submit" }).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "elearning.programmes.withdrawal" }));
  expect(screen.getByRole("button", { name: "elearning.programmes.submit" }).disabled).toBe(true);
});
it("legacy Exchange history links to the Forms-backed opportunity flow without new specialized questions", async () => {
  mount({ initialKind: "exchange" });await screen.findByRole("button", {name:"elearning.programmes.affiliate"});
  expect(screen.queryByRole("button", { name: "elearning.programmes.submit" })).toBeNull();
  expect(screen.getByRole("link",{name:"elearning.exchange.opportunities"}).getAttribute("href")).toBe("/my-learning/exchange");
  expect(screen.queryByLabelText("elearning.programmes.motivation")).toBeNull();
  expect(document.querySelector('[dir="rtl"]')).toBeTruthy();
});
it("owner payout UI sends the observed revision and a reason", async () => {
  const row = { id: "request-1", user_id: 8, payment_method: "PayPal", status: "processing", revision: 3, amount: "50.00", currency: "USD", created_at: "2026-10-10" };
  apiFetch.mockImplementation(async path => ({ ok: true, json: async () => path.includes("members/") ? { user: { name: "Applicant", email: "a@example.com" }, role: "learner", wallet: { verified_sales: 5, threshold: 4, available: "0", currency: "USD" }, referrals: [], withdrawals: [], transactions: [], history: [] } : { items: [row] } }));
  mount({ admin: true, initialKind: "withdrawal",responseId:"request-1" });await screen.findByLabelText("elearning.programmes.note");
  fireEvent.change(screen.getByLabelText("elearning.programmes.note"), { target: { value: "Bank transfer verified" } });
  fireEvent.submit(screen.getByLabelText("elearning.programmes.note").closest("form"));
  await waitFor(() => expect(apiFetch.mock.calls.some(([path, options]) => path.endsWith("/request-1/review") && JSON.parse(options.body).revision === 3 && JSON.parse(options.body).status === "paid")).toBe(true));
});
it("explains how owners enable an unconfigured programme", async () => {
  apiFetch.mockResolvedValue({ ok: false, json: async () => ({ detail: { code: "academy_programmes_disabled" } }) });
  mount({ admin: true });
  expect(await screen.findByRole("link", { name: "elearning.programmes.settings" })).toHaveProperty("pathname", "/e-learning/settings");
});
it.each(['submitted','under_review','approved','suspended'])("does not submit another affiliate application in %s state", async status => {
 apiFetch.mockResolvedValue({ok:true,json:async()=>({...data(),applications:[{id:'a',kind:'affiliate',status,created_at:'2026-10-10',details:{full_name:'Candidate'}}]})});
 mount({affiliateOnly:true});await screen.findByRole('heading',{name:'Candidate'});
 expect(screen.queryByRole('button',{name:'elearning.programmes.submit'})).toBeNull();
 expect(screen.getByRole('link',{name:'elearning.affiliate.dashboard'})).toBeTruthy();
});
