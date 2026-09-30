import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import AdminCommercialStepUp from "./AdminCommercialStepUp";
import { apiFetch } from "../../utils/apiClient";
vi.mock("../../utils/apiClient", async original => ({ ...(await original()), apiFetch: vi.fn() }));
vi.mock("./SecurityMfaPage", () => ({ default: () => <p>Existing enrollment</p> }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
it("verifies an existing factor with the canonical server and does not supply AAL", async () => {
  apiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ factors: [{ id: "factor-id", status: "verified" }] }) }).mockResolvedValueOnce({ ok: true, json: async () => ({ success: true }) });
  const onVerified = vi.fn(); render(<AdminCommercialStepUp onVerified={onVerified} />);
  await screen.findByLabelText("Verification code"); fireEvent.change(screen.getByLabelText("Verification code"), { target: { value: "123456" } }); fireEvent.click(screen.getByRole("button", { name: "Verify account" }));
  await waitFor(() => expect(onVerified).toHaveBeenCalledOnce());
  expect(JSON.parse(apiFetch.mock.calls[1][1].body)).toEqual({ factor_id: "factor-id", code: "123456" });
});
it("retains a controlled failure without claiming verification", async () => {
  apiFetch.mockResolvedValueOnce({ ok: true, json: async () => ({ factors: [{ id: "factor-id", status: "verified" }] }) }).mockResolvedValueOnce({ ok: false, json: async () => ({ detail: "Code rejected" }) });
  const onVerified=vi.fn(); render(<AdminCommercialStepUp onVerified={onVerified} />); await screen.findByLabelText("Verification code"); fireEvent.change(screen.getByLabelText("Verification code"), { target: { value: "123456" } }); fireEvent.click(screen.getByRole("button", { name: "Verify account" })); await screen.findByText("Code rejected"); expect(onVerified).not.toHaveBeenCalled();
});
