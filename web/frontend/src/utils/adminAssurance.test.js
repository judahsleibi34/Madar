import { afterEach, expect, it, vi } from "vitest";
import { apiFetch, registerAdminStepUpHandler } from "./apiClient";
let unregister;
afterEach(() => { unregister?.(); vi.unstubAllGlobals(); });
const denied = code => new Response(JSON.stringify({ detail: { code } }), { status: 403 });
it("ordinary permission denial never invokes step-up", async () => {
  const handler = vi.fn(); unregister = registerAdminStepUpHandler(handler);
  vi.stubGlobal("fetch", vi.fn(async () => denied("permission_denied")));
  expect((await apiFetch("/api/admin/users")).status).toBe(403); expect(handler).not.toHaveBeenCalled();
});
it("a repeatedly challenged read retries at most once and invalidates assurance", async () => {
  const handler = vi.fn(async () => true); unregister = registerAdminStepUpHandler(handler);
  const fetch = vi.fn(async () => denied("aal2_required")); vi.stubGlobal("fetch", fetch);
  expect((await apiFetch("/api/admin/users")).status).toBe(403); expect(fetch).toHaveBeenCalledTimes(2);
});
it("privileged mutations return their rejection without awaiting or replaying", async () => {
  const handler = vi.fn(() => new Promise(() => {})); unregister = registerAdminStepUpHandler(handler);
  const fetch = vi.fn(async () => denied("aal2_required")); vi.stubGlobal("fetch", fetch);
  expect((await apiFetch("/api/admin/users/12", { method: "DELETE", headers: { "X-CSRF-Token": "unit-csrf" } })).status).toBe(403);
  expect(fetch).toHaveBeenCalledOnce(); expect(handler).toHaveBeenCalledOnce();
});
it("tenant endpoints never enter the admin step-up handler", async () => {
  const handler = vi.fn(); unregister = registerAdminStepUpHandler(handler);
  vi.stubGlobal("fetch", vi.fn(async () => denied("aal2_required")));
  await apiFetch("/api/notifications"); expect(handler).not.toHaveBeenCalled();
});
