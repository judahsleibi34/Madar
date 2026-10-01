import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import AdminCommercialPage from "./AdminCommercialPage";
import { commercialRequest } from "../../services/adminCommercialApi";
vi.mock("../../services/adminCommercialApi", async importOriginal => ({ ...(await importOriginal()), commercialRequest: vi.fn() }));
vi.mock("../../utils/apiClient", async original => ({ ...(await original()), apiFetch: vi.fn(async () => ({ ok: true, json: async () => ({ factors: [] }) })) }));
vi.mock("./SecurityMfaPage", () => ({ default: () => <p>Existing MFA security flow</p> }));
const admin = { id: 7, user_type: "admin" };
let state, history;
function fixture(modules = ["website"], amount = 2000) {
  const basis = Object.fromEntries(modules.map(id => [id, { price_book_id: "launch_2026", acquired_at: "2026-09-01T00:00:00Z", paid_since: "2026-09-01T00:00:00Z" }]));
  return { tenant: { brand_name: "Synthetic tenant", owner_name: "Synthetic owner" }, hold: {}, commercial_access: { revision: 17, access_state: "active", review_state: "reviewed", period: { source_type: "complimentary", valid_from: "2026-09-01T00:00:00Z", valid_until: "2027-09-01T00:00:00Z", module_ids: modules }, addons: [] }, entitlements: { assigned_modules: modules, effective_modules: modules, module_commercial_basis: basis, capabilities: ["website_publish"], pricing: { recurring_minor: amount, currency: "USD", billing_interval: "month", price_groups: [{ price_book_id: "launch_2026", module_ids: modules, recurring_minor: amount, grandfathered: true, new_sales_active: false }] } } };
}
function mount(user = admin) { return render(<MemoryRouter initialEntries={["/admin/tenants/42/commercial"]}><Routes><Route path="/admin/tenants/:tenantId/commercial" element={<AdminCommercialPage currentUser={user} />} /></Routes></MemoryRouter>); }
async function ready() { mount(); await screen.findByText("Assigned modules & founding basis"); }
async function open(label) { await ready(); fireEvent.click(screen.getByRole("button", { name: label })); }
beforeEach(() => {
  state = fixture(); history = { payments: [], periods: [], events: [] };
  commercialRequest.mockReset().mockImplementation(async (path, body) => {
    if (path.endsWith("/modules/quote")) return { quote: { revision: 17, module_basis: Object.fromEntries(body.module_ids.map(id => [id, { price_book_id: "launch_2026" }])), pricing: { ...state.entitlements.pricing, module_ids: body.module_ids }, expected_payment_minor: 2000 } };
    if (path.endsWith("/modules") && !body) return structuredClone(state);
    if (path.endsWith("access-history")) return history;
    if (path === "price-books") return { price_books: [{ id: "launch_2026", version: "v2", currency: "USD", billing_interval: "month", standalone_minor: {}, bundle_minor: {}, sales_start_at: null }] };
    return { success: true };
  });
});
afterEach(cleanup);
describe("Platform commercial management", () => {
  it.each([[['forms'],1500], [['website'],2000], [['ecommerce'],2000], [['forms','website'],3000], [['forms','ecommerce'],3000], [['website','ecommerce'],3000], [['forms','website','ecommerce'],4000]])("renders server amount for %j", async (modules, amount) => { state = fixture(modules, amount); await ready(); expect(screen.getByText(`$${(amount/100).toFixed(2)} / month`)).toBeTruthy(); });
  it("renders unavailable pricing and legacy review without invented amounts", async () => { state.entitlements = { assigned_modules: [], capabilities: [], legacy_assignment_requires_review: true, assigned_plan_id: "business_plus" }; await ready(); expect(screen.getByText("Legacy commercial state — Review required")).toBeTruthy(); expect(screen.queryByText("$0.00 / month")).toBeNull(); expect(screen.getByText(/Historical legacy plan: business_plus/)).toBeTruthy(); });
  it("renders mixed synthetic books without calculating prices", async () => { state.entitlements.pricing.recurring_minor = 5700; state.entitlements.pricing.price_groups.push({ price_book_id: "synthetic_2027", module_ids: ["ecommerce"], recurring_minor: 2700, grandfathered: false }); await ready(); expect(screen.getByText("$57.00 / month")).toBeTruthy(); expect(screen.getByText(/synthetic_2027/)).toBeTruthy(); });
  it("shows loading state", () => { commercialRequest.mockReturnValue(new Promise(() => {})); mount(); expect(screen.getByText("Loading commercial state…")).toBeTruthy(); });
  it("does not turn dependency failure into fake inactive data", async () => { commercialRequest.mockRejectedValue(new Error("Dependency unavailable")); mount(); await screen.findByRole("alert"); expect(screen.queryByText("Assigned modules & founding basis")).toBeNull(); });
  it("guides canonical AAL2 step-up", async () => { commercialRequest.mockRejectedValue(Object.assign(new Error("MFA required"), { code: "aal2_required" })); mount(); await screen.findByText("MFA verification required"); expect(await screen.findByText("Existing MFA security flow")).toBeTruthy(); });
  it("hides privileged controls from tenant admins", async () => { mount({ user_type: "user" }); expect(screen.getByText("Platform administrator access required")).toBeTruthy(); expect(screen.queryByRole("button", { name: "Manage modules" })).toBeNull(); });
  it("warns before removing a founding module and needs server quote", async () => { await open("Manage modules"); fireEvent.click(screen.getByRole("checkbox", { name: "Madar Website" })); expect(screen.getByText(/Price-lock warning/)).toBeTruthy(); expect(screen.getByRole("button", { name: "Confirm action" }).disabled).toBe(true); fireEvent.click(screen.getByRole("button", { name: "Preview server quote" })); await screen.findByLabelText("Server quote"); expect(commercialRequest).toHaveBeenCalledWith("tenants/42/modules/quote", { module_ids: [], billing_months: 1 }); });
  it("requires reason and explicit confirmation", async () => { await open("Suspend commercial access"); expect(screen.getByRole("button", { name: "Confirm action" }).disabled).toBe(true); fireEvent.change(screen.getByLabelText("Required reason"), { target: { value: "Nonpayment review" } }); fireEvent.click(screen.getByLabelText(/I have reviewed/)); expect(screen.getByRole("button", { name: "Confirm action" }).disabled).toBe(false); });
  it("submits expected revision and durable key then refreshes", async () => { await open("Suspend commercial access"); fireEvent.change(screen.getByLabelText("Required reason"), { target: { value: "Nonpayment review" } }); fireEvent.click(screen.getByLabelText(/I have reviewed/)); fireEvent.click(screen.getByRole("button", { name: "Confirm action" })); await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull()); const call = commercialRequest.mock.calls.find(([path]) => path.endsWith("/suspend")); expect(call[1].expected_revision).toBe(17); expect(call[1].idempotency_key.length).toBeGreaterThan(16); expect(commercialRequest.mock.calls.filter(([path]) => path === "tenants/42/modules").length).toBe(2); });
  it("retains same key and payload on ambiguous retry", async () => { const base = commercialRequest.getMockImplementation(); commercialRequest.mockImplementation((path, body) => path.endsWith("/suspend") ? Promise.reject(new Error("Network lost")) : base(path, body)); await open("Suspend commercial access"); fireEvent.change(screen.getByLabelText("Required reason"), { target: { value: "Nonpayment review" } }); fireEvent.click(screen.getByLabelText(/I have reviewed/)); fireEvent.click(screen.getByRole("button", { name: "Confirm action" })); await screen.findByText("Network lost"); fireEvent.click(screen.getByRole("button", { name: "Confirm action" })); await waitFor(() => expect(commercialRequest.mock.calls.filter(([path]) => path.endsWith("/suspend")).length).toBe(2)); const calls = commercialRequest.mock.calls.filter(([path]) => path.endsWith("/suspend")); expect(calls[0][1]).toEqual(calls[1][1]); });
  it("refreshes conflict and requires fresh review", async () => { const base = commercialRequest.getMockImplementation(); commercialRequest.mockImplementation((path, body) => path.endsWith("/suspend") ? Promise.reject(Object.assign(new Error("Stale revision"), { status: 409 })) : base(path, body)); await open("Suspend commercial access"); fireEvent.change(screen.getByLabelText("Required reason"), { target: { value: "Nonpayment review" } }); fireEvent.click(screen.getByLabelText(/I have reviewed/)); fireEvent.click(screen.getByRole("button", { name: "Confirm action" })); await screen.findByText(/State refreshed/); expect(screen.getByRole("button", { name: "Confirm action" }).disabled).toBe(true); });
  it("distinguishes hold and reactivation from payment", async () => { state.hold = { commercial_suspended_at: "2026-09-02T00:00:00Z", commercial_suspension_reason: "Review pending" }; await open("Reactivate commercial access"); expect(screen.getByText(/Does not record payment, extend expired access/)).toBeTruthy(); expect(screen.queryByRole("button", { name: "Suspend commercial access" })).toBeNull(); });
  it("labels complimentary coverage distinctly", async () => { await open("Grant complimentary access"); expect(screen.getByText(/not a zero-dollar payment/)).toBeTruthy(); });
  it("shows corrections without hiding originals", async () => { history.payments = [{ id: "original", actual_minor: 2000, receipt_reference: "ORIGINAL" }, { id: "correction", actual_minor: 2100, receipt_reference: "CORRECTED", corrects_payment_id: "original" }]; await ready(); expect(screen.getByText("ORIGINAL")).toBeTruthy(); expect(screen.getByText("CORRECTED")).toBeTruthy(); });
  it("has read-only prepared price books without activation", async () => { await ready(); expect(screen.getByText(/Prepared — not activated/)).toBeTruthy(); expect(screen.queryByRole("button", { name: /Activate/ })).toBeNull(); });
  it("keeps expired access visibly expired", async () => { state.commercial_access.access_state = "expired"; state.commercial_access.period = null; await ready(); expect(screen.getByText("expired")).toBeTruthy(); expect(screen.getByText("No current access period")).toBeTruthy(); });
});

it.each(["Record manual payment", "Grant complimentary access", "Revoke access", "Correct payment evidence", "Review as inactive"])("opens the canonical %s action with mandatory review", async label => {
  await open(label); expect(screen.getByLabelText("Required reason")).toBeTruthy(); expect(screen.getByRole("button", { name: "Confirm action" }).disabled).toBe(true);
});
it("blocks a first payment under prepared launch pricing after server preview", async () => {
  await open("Record manual payment"); fireEvent.click(screen.getByRole("button", { name: "Preview server quote" })); await screen.findByLabelText("Server quote"); expect(screen.getByText(/This basis is not eligible for payment/)).toBeTruthy(); expect(screen.getByRole("button", { name: "Confirm action" }).disabled).toBe(true);
});

it("pins assignment to the previewed price books instead of silently choosing another book", async () => {
  await open("Manage modules"); fireEvent.click(screen.getByRole("button", { name: "Preview server quote" })); await screen.findByLabelText("Server quote"); fireEvent.change(screen.getByLabelText("Required reason"), { target: { value: "Explicit reviewed mapping" } });
  fireEvent.click(screen.getByRole("button", { name: "Preview server quote" })); await screen.findByLabelText("Server quote"); fireEvent.click(screen.getByLabelText(/I have reviewed/)); fireEvent.click(screen.getByRole("button", { name: "Confirm action" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull()); expect(commercialRequest.mock.calls.find(([path, body]) => path.endsWith("/modules") && body)[1].price_books).toEqual({ website: "launch_2026" });
});

it("discards an in-flight quote when the proposed module set changes", async () => {
  const base = commercialRequest.getMockImplementation();
  let resolveQuote;
  commercialRequest.mockImplementation((path, body) => path.endsWith("/modules/quote") ? new Promise(resolve => { resolveQuote = () => resolve({ quote: { revision: 17, module_basis: { website: { price_book_id: "launch_2026" } }, pricing: { ...state.entitlements.pricing, module_ids: body.module_ids } } }); }) : base(path, body));
  await open("Manage modules");
  fireEvent.click(screen.getByRole("button", { name: "Preview server quote" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "Madar Forms" }));
  resolveQuote();
  await waitFor(() => expect(screen.getByRole("button", { name: "Preview server quote" }).disabled).toBe(false));
  expect(screen.queryByLabelText("Server quote")).toBeNull();
  expect(screen.getByRole("button", { name: "Confirm action" }).disabled).toBe(true);
});
