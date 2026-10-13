import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import i18n from "../../i18n";
import { apiFetch } from "../../utils/apiClient";
import { AcademyAuditLogPage, MemberControls, RewardReviewControl } from "./AcademyAdminControls";

vi.mock("../../utils/apiClient", () => ({ apiFetch: vi.fn(), getApiUrl: path => path }));
const ok = body => Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
beforeEach(async () => { await i18n.changeLanguage("en"); apiFetch.mockImplementation(() => ok({})); });
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("approves a pending reward, and rejecting needs a reason", async () => {
  const done = vi.fn();
  render(<RewardReviewControl referralId="r1" onDone={done} />);
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  await waitFor(() => expect(done).toHaveBeenCalled());
  expect(apiFetch).toHaveBeenCalledWith("/elearning/owner/rewards/r1/review", expect.objectContaining({ method: "POST", body: JSON.stringify({ decision: "earned", note: "" }) }));
  fireEvent.click(screen.getByRole("button", { name: "Reject" }));
  expect(screen.getByRole("button", { name: "Reject reward" }).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Reason"), { target: { value: "Duplicate purchase" } });
  fireEvent.click(screen.getByRole("button", { name: "Reject reward" }));
  await waitFor(() => expect(apiFetch).toHaveBeenLastCalledWith("/elearning/owner/rewards/r1/review", expect.objectContaining({ body: JSON.stringify({ decision: "rejected", note: "Duplicate purchase" }) })));
});

it("verifies a PAU student manually and saves a Tuition override only with a reason", async () => {
  render(<MemberControls learner={{ user_id: 7, institution_verified: true, institution_manually_verified: false, tuition_override: null }} institutionLabel="PAU Student" />);
  fireEvent.click(screen.getByRole("button", { name: "Mark as Verified PAU Student" }));
  await waitFor(() => expect(apiFetch).toHaveBeenCalledWith("/elearning/owner/members/7/institution-verification", expect.objectContaining({ method: "PUT", body: JSON.stringify({ verified: true, note: "" }) })));
  fireEvent.change(screen.getByLabelText("Eligibility"), { target: { value: "eligible" } });
  expect(screen.getByRole("button", { name: "Save eligibility" }).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText("Reason (required, saved in the audit log)"), { target: { value: "Board decision 12/10" } });
  fireEvent.click(screen.getByRole("button", { name: "Save eligibility" }));
  await waitFor(() => expect(apiFetch).toHaveBeenLastCalledWith("/elearning/owner/members/7/tuition-override", expect.objectContaining({ body: JSON.stringify({ eligible: true, reason: "Board decision 12/10" }) })));
});

it("lists audit entries newest first", async () => {
  apiFetch.mockImplementation(() => ok({ entries: [{ id: "a", created_at: "2026-10-13T10:00:00Z", action: "academy.tuition_override.set", target_type: "academy_member", target_id: "7", actor_name: "Owner Name", metadata: { reason: "Board decision" } }], has_more: false }));
  render(<MemoryRouter><AcademyAuditLogPage /></MemoryRouter>);
  expect(await screen.findByText("academy.tuition_override.set")).toBeTruthy();
  expect(screen.getByText("Owner Name")).toBeTruthy();
  expect(screen.getByText("reason: Board decision")).toBeTruthy();
});
