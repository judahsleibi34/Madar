import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import RecoveryBanner from "./RecoveryBanner";
import { apiFetch } from "../../utils/apiClient";
vi.mock("../../utils/apiClient", () => ({ apiFetch: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
describe("RecoveryBanner", () => {
  it("shows a visible restriction only when the backend declares recovery", async () => {
    apiFetch.mockResolvedValue({ ok: true, json: async () => ({ restricted: true }) });
    render(<RecoveryBanner />);
    expect((await screen.findByRole("status")).textContent).toContain("Business changes are paused");
    expect(apiFetch).toHaveBeenCalledWith("/api/health/recovery");
  });
  it("does not claim recovery for a normal runtime", async () => {
    apiFetch.mockResolvedValue({ ok: true, json: async () => ({ restricted: false }) });
    render(<RecoveryBanner />);
    await vi.waitFor(() => expect(apiFetch).toHaveBeenCalled());
    expect(screen.queryByRole("status")).toBeNull();
  });
});
