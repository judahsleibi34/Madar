import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import PlatformAdminGate from "./PlatformAdminGate";
import UserManagementPage from "./UserManagementPage";
import Dashboard from "./Dashboard";
import { clearCsrfToken } from "../../utils/apiClient";

vi.mock("react-i18next", () => ({ useTranslation: () => ({ t: key => key }) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); clearCsrfToken(); });
const user = { id: 7, user_type: "admin", account_kind: "platform" };
const response = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
const denied = () => response({ detail: { code: "aal2_required", message: "Verify MFA" } }, 403);
function mockApi({ level = "aal2", noFactor = false, readChallenge = false, mutationChallenge = false, fail = false, stuck = false } = {}) {
  let reads = 0, mutations = 0;
  const fetch = vi.fn(async (url, init = {}) => {
    if (url.endsWith("/auth/mfa/status")) return response({ aal: { current_level: level }, factors: noFactor ? [] : [{ id: "factor", status: "verified", factor_type: "totp" }] });
    if (url.endsWith("/auth/user_status")) return response({ csrf_token: "unit-csrf" });
    if (url.endsWith("/auth/mfa/enroll/verify")) { level = stuck ? "aal1" : "aal2"; return response({ success: true }); }
    if (url.includes("/admin/users")) {
      if (["PATCH", "DELETE"].includes(init.method)) { mutations++; return mutationChallenge && mutations === 1 ? denied() : response({ success: true }); }
      reads++;
      if (fail) return response({ detail: "Unavailable" }, 503);
      if (readChallenge && reads === 1) { level = "aal1"; return denied(); }
      return response({ users: [{ id: 12, first_name: "Actual", email: "actual@example.invalid", user_type: "user" }], pagination: { total_count: 1, page: 1 } });
    }
    throw new Error(`Unexpected API ${url}`);
  });
  vi.stubGlobal("fetch", fetch);
  return { reads: () => reads, mutations: () => mutations };
}
function show(children) { return render(<MemoryRouter><PlatformAdminGate user={user}>{children}</PlatformAdminGate></MemoryRouter>); }
async function verify() {
  await screen.findByLabelText("Verification code");
  fireEvent.change(screen.getByLabelText("Verification code"), { target: { value: "123456" } });
  fireEvent.click(screen.getByRole("button", { name: "Verify account" }));
}
it("AAL1 direct entry gates the application until authoritative AAL2", async () => {
  mockApi({ level: "aal1" }); show(<p>Protected application</p>);
  await screen.findByText("MFA verification required"); expect(screen.queryByText("Protected application")).toBeNull();
  await verify(); await screen.findByText("Protected application");
});
it("AAL2 renders ordinary admin content", async () => {
  mockApi(); show(<p>Protected application</p>); await screen.findByText("Protected application");
});
it("no verified factor exposes enrollment without privileged content", async () => {
  mockApi({ level: "aal1", noFactor: true }); show(<p>Protected application</p>);
  await screen.findByText("securityMfa.actions.start"); expect(screen.queryByText("Protected application")).toBeNull();
});
it("a successful verification response alone never establishes AAL2", async () => {
  mockApi({ level: "aal1", stuck: true }); show(<p>Protected application</p>); await verify();
  await waitFor(() => expect(screen.getByRole("button", { name: "Verify account" }).disabled).toBe(false));
  expect(screen.queryByText("Protected application")).toBeNull();
});
it("users GET retries exactly once after step-up", async () => {
  const counts = mockApi({ readChallenge: true }); show(<UserManagementPage currentUser={user} />);
  await verify(); await screen.findByText("Actual"); expect(counts.reads()).toBe(2);
});
it("failed users request never reports authoritative zero or empty users", async () => {
  mockApi({ fail: true }); show(<UserManagementPage currentUser={user} />);
  await screen.findAllByText("Could not load users.");
  expect(document.querySelector(".user-management-stats")).toBeNull();
  expect(document.querySelector(".user-management-empty")).toBeNull();
});
it("role mutation is not replayed and stale role selection is revoked", async () => {
  const counts = mockApi({ mutationChallenge: true }); show(<UserManagementPage currentUser={user} />);
  await screen.findByText("Actual");
  fireEvent.change(screen.getByLabelText("Role"), { target: { value: "admin" } });
  fireEvent.click(screen.getByRole("button", { name: "Save role" }));
  await verify(); await waitFor(() => expect(screen.getByLabelText("Role").value).toBe("user"));
  expect(counts.mutations()).toBe(1);
  fireEvent.change(screen.getByLabelText("Role"), { target: { value: "admin" } }); fireEvent.click(screen.getByRole("button", { name: "Save role" }));
  await waitFor(() => expect(counts.mutations()).toBe(2));
});
it("dashboard shows truthful unavailable metrics without demo KPIs when its source fails", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ detail: "Unavailable" }, 503)));
  render(<MemoryRouter><Dashboard /></MemoryRouter>);
  await waitFor(() => expect(screen.getAllByText(/Not available/)).toHaveLength(4));
  for (const fake of ["4,862", "$62.4K", "99.98%", "1,284", "6,420", "142ms", "18"]) expect(screen.queryByText(fake)).toBeNull();
});

it("delete confirmation is revoked and deletion never replays after step-up", async () => {
  const counts = mockApi({ mutationChallenge: true }); show(<UserManagementPage currentUser={user} />);
  await screen.findByText("Actual");
  fireEvent.click(screen.getByRole("button", { name: "Delete", exact: true }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm delete", exact: true }));
  await verify(); await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  expect(counts.mutations()).toBe(1);
});

it("dashboard renders only an exact authoritative users count", async () => {
  vi.stubGlobal("fetch", vi.fn(async () => response({ pagination: { total_count: 56 } })));
  render(<MemoryRouter><Dashboard /></MemoryRouter>);
  await screen.findByText("56"); expect(screen.getAllByText(/Not available/)).toHaveLength(3);
});
