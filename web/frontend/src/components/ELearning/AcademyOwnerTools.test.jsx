import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { MemoryRouter,Routes,Route } from "react-router-dom";
import i18n from "../../i18n";
import AcademyOwnerOverview from "./AcademyOwnerOverview";
import AcademyExchangeOpportunities from "./AcademyExchangeOpportunities";
import AcademySupportDocuments from "./AcademySupportDocuments";
import AcademyContactInbox from "./AcademyContactInbox";
import { academyOwnerApi } from "./academyOwnerApi";
vi.mock("./academyOwnerApi", () => ({ academyOwnerApi: vi.fn() }));
beforeEach(async () => { await i18n.changeLanguage("en");academyOwnerApi.mockReset(); });
afterEach(cleanup);
const mount = element => render(<MemoryRouter>{element}</MemoryRouter>);
it("renders owner metrics without inventing hidden financial fields", async () => {
  academyOwnerApi.mockResolvedValue({ total_learners: 7, active_learners: 4, enrollments: 9, certificates: 2, applications: [], recent_activity: [] });
  mount(<AcademyOwnerOverview />);await screen.findByText("Total learners");expect(screen.getByText("7")).toBeTruthy();expect(screen.queryByText("Rewards")).toBeNull();
});
it("saves an opportunity draft using server revision then permits closing", async () => {
  academyOwnerApi.mockImplementation(async (path, options) => options ? { id: "one" } : { items: [{ id: "one", title: "University Exchange", status: "published", revision: 4 }] });
  render(<MemoryRouter initialEntries={["/exchange/one/edit"]}><Routes><Route path="/exchange/:id/edit" element={<AcademyExchangeOpportunities editing/>}/></Routes></MemoryRouter>);await screen.findByDisplayValue("University Exchange");
  fireEvent.change(screen.getByLabelText("Status"), { target: { value: "closed" } });fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));
  await waitFor(() => expect(academyOwnerApi).toHaveBeenCalledWith("/exchange/one", expect.objectContaining({ method: "PUT", body: expect.objectContaining({ status: "closed", expected_revision: 4 }) })));
});
it("private document owner review offers download and no applicant mutation", async () => {
  academyOwnerApi.mockResolvedValue({ items: [{ id: "doc", filename: "document.pdf", size_bytes: 20 }] });
  mount(<AcademySupportDocuments application={{ id: "app" }} />);fireEvent.click(await screen.findByRole("button", { name: /document.pdf/ }));
  await waitFor(() => expect(academyOwnerApi).toHaveBeenCalledWith("/applications/app/documents/doc", { download: "document.pdf" }));
  expect(screen.queryByRole("button", { name: "Remove" })).toBeNull();expect(screen.queryByLabelText("Upload document")).toBeNull();
});
it("applicant uploads documents only through the private application endpoint", async () => {
  academyOwnerApi.mockResolvedValue({ items: [] });mount(<AcademySupportDocuments application={{ id: "app" }} editable />);
  const file = new File(["pdf"], "proof.pdf", { type: "application/pdf" });fireEvent.change(screen.getByLabelText("Upload document"), { target: { files: [file] } });fireEvent.click(screen.getByRole("button", { name: "Upload document" }));
  await waitFor(() => expect(academyOwnerApi).toHaveBeenCalledWith("/applications/app/documents", { method: "POST", file }));
});
it("contact inbox opens the message and uses the tenant-bound read command", async () => {
  academyOwnerApi.mockResolvedValue({ items: [{ id: 1, name: "Student", subject: "Question", email: "student@example.com", message: "Please help", created_at: "2026-10-11", read_at: null }] });
  render(<MemoryRouter initialEntries={["/contacts/1"]}><Routes><Route path="/contacts/:contactId" element={<AcademyContactInbox detail/>}/></Routes></MemoryRouter>);expect(await screen.findByText("Please help")).toBeTruthy();fireEvent.click(screen.getByRole("button", { name: "Mark read" }));
  await waitFor(() => expect(academyOwnerApi).toHaveBeenCalledWith("/contacts/1/read", { method: "PUT", body: { read: true } }));
});
