import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import ELearningPlansPage from "./ELearningPlansPage";
import ELearningCatalog, { MyLearningPlans } from "./ELearningCatalog";
import { ELearningTerminologyContext } from "../../context/ELearningTerminologyContext";
import { getELearningTerminology } from "../../config/elearningTerminology";
import * as api from "../../services/elearningCommerce";
import { fetchCourses } from "../../services/elearningCourses";
vi.mock("../../services/elearningCommerce", () => ({ fetchPlans: vi.fn(), savePlan: vi.fn(), fetchCatalog: vi.fn(), fetchMyPlans: vi.fn(), enrollCatalogCourse: vi.fn(), createCheckout: vi.fn(), localPaymentEvent: vi.fn() }));
vi.mock("../../services/elearningCourses", () => ({ fetchCourses: vi.fn() }));
const plan = { id: "p", name: "Lifetime All Access", description: "", amount: 49, currency: "USD", billing_type: "one_time", access_scope: "all_courses", status: "active", revision: 1, course_ids: [] };
const course = { id: "c", name: "English Communication", description: "Practice", cover_asset: "", cta: { action: "buy" }, plans: ["p"] };
const account = { local_adapter: true, entitlements: [], checkouts: [] };
function page(element) { return render(<MemoryRouter><ELearningTerminologyContext.Provider value={{ labels: getELearningTerminology({ course_label: "Program" }) }}><Routes><Route path="/" element={element} /><Route path="/my-learning/courses/c" element={<h1>Course Player</h1>} /></Routes></ELearningTerminologyContext.Provider></MemoryRouter>); }
beforeEach(async () => {
  await i18n.changeLanguage("en");
  HTMLDialogElement.prototype.showModal = vi.fn(function () { this.setAttribute("open", ""); });
  api.fetchPlans.mockResolvedValue({ plans: [plan] });fetchCourses.mockResolvedValue({ courses: [course], has_more: false });
  api.fetchCatalog.mockResolvedValue({ courses: [course], plans: [plan], local_adapter: true });
  api.fetchMyPlans.mockResolvedValue(account);api.savePlan.mockResolvedValue({ plans: [plan] });
  api.createCheckout.mockResolvedValue({ checkout: { id: "checkout", terms: plan, requested_resource_id: "c" } });
  api.localPaymentEvent.mockResolvedValue({});api.enrollCatalogCourse.mockResolvedValue({ enrollment_id: "enrollment" });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });
it("keeps billing independent from scope, uses Program labels and saves an all-access price", async () => {
  page(<ELearningPlansPage />);fireEvent.click(await screen.findByRole("button", { name: "Add Plan" }));
  fireEvent.change(screen.getByLabelText("Plan Name"), { target: { value: "All Programs" } });
  fireEvent.change(screen.getByLabelText("Course Access"), { target: { value: "all_courses" } });
  expect(screen.getByLabelText("Billing Type").value).toBe("one_time");
  fireEvent.change(screen.getByLabelText("Billing Type"), { target: { value: "monthly" } });
  expect(screen.getByLabelText("Course Access").value).toBe("all_courses");
  fireEvent.change(screen.getByLabelText("Billing Type"), { target: { value: "one_time" } });
  fireEvent.change(screen.getByLabelText("Price"), { target: { value: "49.00" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(api.savePlan).toHaveBeenCalledWith(expect.objectContaining({ billing_type: "one_time", access_scope: "all_courses", amount: "49.00", course_ids: [] })));
});
it("edits archive/restore sale status without changing historical purchases", async () => {
  page(<ELearningPlansPage />);fireEvent.click(await screen.findByRole("button", { name: "Edit Plan" }));
  fireEvent.change(screen.getByLabelText("Plan Status"), { target: { value: "archived" } });
  fireEvent.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(api.savePlan).toHaveBeenCalledWith(expect.objectContaining({ id: "p", status: "archived", revision: 1 })));
});
it("shows server-resolved included access and enrolls without creating checkout", async () => {
  api.fetchCatalog.mockResolvedValue({ courses: [{ ...course, cta: { action: "enroll", included_in: { name: plan.name } } }], plans: [plan] });
  page(<ELearningCatalog />);await screen.findByText("Included in Lifetime All Access");fireEvent.click(screen.getByRole("button", { name: "Enroll in Program" }));
  await screen.findByRole("heading", { name: "Course Player" });expect(api.enrollCatalogCourse).toHaveBeenCalledWith("c");expect(api.createCheckout).not.toHaveBeenCalled();
});
it("keeps failed checkout unfulfilled and waits for server payment confirmation", async () => {
  page(<ELearningCatalog />);fireEvent.click(await screen.findByRole("button", { name: "View Plans / Buy" }));
  fireEvent.click(screen.getByRole("button", { name: "Buy" }));await screen.findByText("Checkout: Lifetime All Access");
  expect(api.enrollCatalogCourse).not.toHaveBeenCalled();fireEvent.click(screen.getByRole("button", { name: "Fail Test Payment" }));
  await screen.findByText("Payment failed. No paid access was granted.");expect(screen.queryByText("Course Player")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Confirm Test Payment" }));await screen.findByText("Course Player");
  expect(api.localPaymentEvent).toHaveBeenCalledWith("checkout", "paid");
});
it("offers free enrollment, suspension state, and standalone access plans without enrollment", async () => {
  api.fetchCatalog.mockResolvedValue({ courses: [{ ...course, cta: { action: "enroll_free" } }, { ...course, id: "s", name: "Suspended", cta: { action: "suspended" } }], plans: [plan], local_adapter: true });
  page(<ELearningCatalog />);await screen.findByRole("button", { name: "Enroll Free" });expect(screen.getByText("Access Suspended")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Browse Access Plans" }));fireEvent.click(screen.getByRole("button", { name: "Buy" }));
  await waitFor(() => expect(api.createCheckout).toHaveBeenCalledWith("p", undefined, expect.any(String)));
});
it("shows preserved purchase-time terms and subscription lifecycle actions", async () => {
  api.fetchMyPlans.mockResolvedValue({ ...account, entitlements: [{ id: "e", checkout_id: "ch", terms: { ...plan, name: "Monthly All Access", billing_type: "monthly" }, effective_status: "active", expires_at: "2030-01-01T00:00:00Z" }] });
  page(<MyLearningPlans />);await screen.findByText("Monthly All Access");fireEvent.click(screen.getByRole("button", { name: "Test Subscription Expiry" }));
  await waitFor(() => expect(api.localPaymentEvent).toHaveBeenCalledWith("ch", "expired", false));expect(screen.getByText(/49.00 USD/)).toBeTruthy();
});
it("uses the global skeleton and hides local payment actions when the adapter is unavailable", async () => {
  api.fetchCatalog.mockReturnValue(new Promise(() => {}));const { container } = page(<ELearningCatalog />);expect(container.querySelector(".elearning-skeleton")).toBeTruthy();cleanup();
  api.fetchCatalog.mockResolvedValue({ courses: [course], plans: [plan], local_adapter: false });page(<ELearningCatalog />);
  fireEvent.click(await screen.findByRole("button", { name: "View Plans / Buy" }));expect(screen.getByRole("button", { name: "Buy" }).disabled).toBe(true);expect(screen.queryByText("Confirm Test Payment")).toBeNull();
});


it('uses course checkbox rows while enforcing single-course selection and supports store currencies', async () => {
 fetchCourses.mockResolvedValue({ courses: [{ ...course, status: 'published' }, { ...course, id: 'other', name: 'Another Course', status: 'published' }], has_more: false });
 page(<ELearningPlansPage />); fireEvent.click(await screen.findByRole('button', { name: 'Add Plan' }));
 const currencies = screen.getByLabelText('Currency');
 expect(currencies.tagName).toBe('SELECT');
 expect([...currencies.options].map(option => option.value)).toEqual(['ILS', 'JOD', 'USD', 'EUR']);
 fireEvent.change(currencies, { target: { value: 'JOD' } });
 const first = screen.getByRole('checkbox', { name: 'English Communication' });
 const second = screen.getByRole('checkbox', { name: 'Another Course' });
 fireEvent.click(first); expect(first.checked).toBe(true);
 fireEvent.click(second); expect(first.checked).toBe(false); expect(second.checked).toBe(true);
 fireEvent.click(second); expect(second.checked).toBe(false); expect(screen.getByRole('button', { name: 'Save' }).disabled).toBe(true);
 fireEvent.change(screen.getByLabelText('Course Access'), { target: { value: 'selected_courses' } });
 fireEvent.click(first); fireEvent.click(second);
 expect(first.checked).toBe(true); expect(second.checked).toBe(true);
 fireEvent.change(screen.getByLabelText('Plan Name'), { target: { value: 'Two Courses' } });
 fireEvent.click(screen.getByRole('button', { name: 'Save' }));
 await waitFor(() => expect(api.savePlan).toHaveBeenCalledWith(expect.objectContaining({ currency: 'JOD', course_ids: ['c', 'other'], access_scope: 'selected_courses' })));
});
