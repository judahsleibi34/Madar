import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "../../../../utils/apiClient";
import { uiText } from "../constants/uiText";
import ApiSourceManagementPanel from "./ApiSourceManagementPanel";

vi.mock("../../../../utils/apiClient", async (importOriginal) => ({
  ...(await importOriginal()), apiFetch: vi.fn(),
}));

const response = (body, status = 200) => ({
  ok: status >= 200 && status < 300, status,
  headers: { get: () => "application/json" }, json: async () => body,
});

const source = { id: "source-1", source_type: "api_provider", provider_key: "approved_provider", resource_type: "orders" };
const resourceBody = (overrides = {}) => ({
  available: true, provider_registered: true, checkpoint_capable: true,
  items: [{
    id: "resource-1", resource_key: "orders", dataset_id: "dataset-1", committed_revision: 4,
    latest_successful_ingestion: { status: "succeeded", completed_at: "2026-10-20T10:00:00Z" },
    latest_ingestion: { status: "succeeded", completed_at: "2026-10-20T10:00:00Z" },
    latest_checkpoint: { status: "ready", target_revision: 3, version_id: "version-3" },
  }], ...overrides,
});
const schedule = (overrides = {}) => ({
  id: "schedule-1", source_resource_id: "resource-1", enabled: false,
  interval_seconds: 3600, status: "disabled", fence: 2,
  last_attempt_at: null, last_success_at: null, next_due_at: null,
  last_error_category: null, ...overrides,
});
const mount = (props = {}) => render(<ApiSourceManagementPanel
  registryPath="http://api/users/7/data/projects/project-1/sources"
  source={source} t={uiText.en} {...props}
/>);

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("ApiSourceManagementPanel", () => {
  it("shows authoritative connection, revision, and checkpoint freshness without secrets", async () => {
    apiFetch.mockImplementation((url) => {
      if (url.includes("/resources?")) return Promise.resolve(response(resourceBody()));
      if (url.endsWith("/credentials")) return Promise.resolve(response({ items: [{
        credential_id: "credential-1", status: "active", credential_type: "bearer",
        expires_at: "2099-01-01T00:00:00Z",
      }] }));
      return Promise.resolve(response({ available: true, schedule: schedule() }));
    });
    mount();
    expect(await screen.findByText("Ready")).toBeTruthy();
    expect(screen.getByText("Latest revision is not ready for analysis")).toBeTruthy();
    expect(screen.getByText(/Ready · revision 3/)).toBeTruthy();
    expect(screen.getByText("4")).toBeTruthy();
    expect(document.body.textContent).not.toContain("credential-1");
    expect(document.body.textContent).not.toMatch(/bearer/i);
  });

  it("uses the authorized schedule endpoint to enable and disable synchronization", async () => {
    let enabled = false;
    apiFetch.mockImplementation((url, options = {}) => {
      if (url.includes("/resources?")) return Promise.resolve(response(resourceBody()));
      if (url.endsWith("/credentials")) return Promise.resolve(response({ items: [{ status: "active" }] }));
      if (options.method === "PUT") {
        enabled = JSON.parse(options.body).enabled;
        return Promise.resolve(response({ available: true, schedule: schedule({
          enabled, status: enabled ? "idle" : "disabled",
          next_due_at: enabled ? "2026-10-21T12:00:00Z" : null,
        }) }));
      }
      return Promise.resolve(response({ available: true, schedule: schedule() }));
    });
    mount();
    const toggle = await screen.findByRole("checkbox", { name: uiText.en.sourceAutomaticSync });
    fireEvent.click(toggle);
    fireEvent.change(screen.getByRole("combobox", { name: uiText.en.sourceSyncInterval }), { target: { value: "900" } });
    fireEvent.click(screen.getByRole("button", { name: uiText.en.sourceSyncSave }));
    expect(await screen.findByText(uiText.en.sourceSyncSaved)).toBeTruthy();
    const firstPut = apiFetch.mock.calls.find(([, options]) => options?.method === "PUT");
    expect(JSON.parse(firstPut[1].body)).toEqual({ enabled: true, interval_seconds: 900, expected_fence: 2 });
    fireEvent.click(toggle);
    fireEvent.click(screen.getByRole("button", { name: uiText.en.sourceSyncSave }));
    await waitFor(() => expect(apiFetch.mock.calls.filter(([, options]) => options?.method === "PUT")).toHaveLength(2));
    expect(enabled).toBe(false);
  });

  it.each([
    [401, "Authentication required"], [403, "Not allowed"],
    [409, uiText.en.sourceSyncConflict], [503, uiText.en.sourceSyncUpgrade],
  ])("shows schedule write errors for HTTP %s", async (httpStatus, message) => {
    apiFetch.mockImplementation((url, options = {}) => {
      if (url.includes("/resources?")) return Promise.resolve(response(resourceBody()));
      if (url.endsWith("/credentials")) return Promise.resolve(response({ items: [{ status: "active" }] }));
      if (options.method === "PUT") {
        return Promise.resolve(response({ detail: httpStatus < 409 ? { message } : {} }, httpStatus));
      }
      return Promise.resolve(response({ available: true, schedule: schedule() }));
    });
    mount();
    await screen.findByRole("checkbox");
    fireEvent.click(screen.getByRole("button", { name: uiText.en.sourceSyncSave }));
    expect(await screen.findByText(message)).toBeTruthy();
  });

  it.each([
    [[], uiText.en.sourceCredential_missing],
    [[{ status: "revoked" }], uiText.en.sourceCredential_revoked],
    [[{ status: "active", expires_at: "2020-01-01T00:00:00Z" }], uiText.en.sourceCredential_expired],
  ])("blocks schedule controls for unsafe credential state", async (items, label) => {
    apiFetch.mockImplementation((url) => {
      if (url.includes("/resources?")) return Promise.resolve(response(resourceBody()));
      if (url.endsWith("/credentials")) return Promise.resolve(response({ items }));
      return Promise.resolve(response({ available: true, schedule: schedule() }));
    });
    mount();
    expect(await screen.findByText(label)).toBeTruthy();
    expect(screen.getByRole("checkbox").disabled).toBe(true);
    expect(screen.getByRole("button", { name: uiText.en.sourceSyncSave }).disabled).toBe(true);
  });

  it("disables scheduling when schema 156 or provider registration is unavailable", async () => {
    apiFetch.mockImplementation((url) => {
      if (url.includes("/resources?")) return Promise.resolve(response(resourceBody({ provider_registered: false })));
      if (url.endsWith("/credentials")) return Promise.resolve(response({ items: [{ status: "active" }] }));
      return Promise.resolve(response({ available: false, schedule: null }));
    });
    mount();
    expect(await screen.findByText(uiText.en.sourceProviderUnavailableHelp)).toBeTruthy();
    expect(screen.getByText(uiText.en.sourceSyncUpgrade)).toBeTruthy();
    expect(screen.getByRole("checkbox").disabled).toBe(true);
  });

  it("submits a credential only to the authorized vault endpoint and clears it", async () => {
    let credentialReady = false;
    apiFetch.mockImplementation((url, options = {}) => {
      if (url.includes("/resources?")) return Promise.resolve(response(resourceBody()));
      if (url.endsWith("/credentials") && options.method === "POST") {
        credentialReady = true;
        return Promise.resolve(response({ status: "active", credential_version: 1 }, 201));
      }
      if (url.endsWith("/credentials")) return Promise.resolve(response({
        items: credentialReady ? [{ status: "active" }] : [],
      }));
      return Promise.resolve(response({ available: true, schedule: schedule() }));
    });
    mount({ capabilities: { credential_vault_available: true } });
    const input = await screen.findByLabelText(new RegExp(uiText.en.sourceCredentialToken));
    fireEvent.change(input, { target: { value: "browser-only-secret" } });
    fireEvent.click(screen.getByRole("button", { name: uiText.en.sourceCredentialSave }));
    expect(await screen.findByText(uiText.en.sourceCredentialSaved)).toBeTruthy();
    const request = apiFetch.mock.calls.find(([, options]) => options?.method === "POST");
    expect(request[0]).toMatch(/\/credentials$/);
    expect(JSON.parse(request[1].body)).toEqual({
      credential_type: "bearer", secret: "browser-only-secret",
    });
    expect(document.body.textContent).not.toContain("browser-only-secret");
  });

  it("uses the existing incremental ingestion path to validate and prepare a new resource", async () => {
    let initialized = false;
    apiFetch.mockImplementation((url, options = {}) => {
      if (url.includes("/resources?")) {
        return Promise.resolve(response(initialized ? resourceBody() : resourceBody({ items: [] })));
      }
      if (url.endsWith("/credentials")) {
        return Promise.resolve(response({ items: [{ status: "active", source_revision: 1 }] }));
      }
      if (url.includes("/ingestions/api") && options.method === "POST") {
        initialized = true;
        return Promise.resolve(response({ committed_revision: 1, persistent_dataset_id: "dataset-1" }, 201));
      }
      return Promise.resolve(response({ available: true, schedule: schedule() }));
    });
    mount({ capabilities: { incremental_resources_available: true } });
    const button = await screen.findByRole("button", { name: uiText.en.sourceConnectionInitialize });
    fireEvent.click(button);
    expect(await screen.findByText(uiText.en.sourceConnectionInitialized)).toBeTruthy();
    const request = apiFetch.mock.calls.find(([url, options]) => url.includes("/ingestions/api") && options?.method === "POST");
    expect(request[0]).toContain("resource_type=orders");
    expect(request[1].headers["Idempotency-Key"]).toBeTruthy();
    expect(await screen.findByRole("checkbox", { name: uiText.en.sourceAutomaticSync })).toBeTruthy();
  });

  it("revokes the active credential with its current source revision", async () => {
    let revoked = false;
    apiFetch.mockImplementation((url, options = {}) => {
      if (url.includes("/resources?")) return Promise.resolve(response(resourceBody()));
      if (url.endsWith("/credentials/revoke") && options.method === "POST") {
        revoked = true;
        return Promise.resolve(response({ status: "revoked", source_revision: 8 }));
      }
      if (url.endsWith("/credentials")) return Promise.resolve(response({
        items: [{ status: revoked ? "revoked" : "active", source_revision: revoked ? 8 : 7 }],
      }));
      return Promise.resolve(response({ available: true, schedule: schedule() }));
    });
    mount();
    fireEvent.click(await screen.findByRole("button", { name: uiText.en.sourceCredentialRevoke }));
    expect(await screen.findByText(uiText.en.sourceCredentialRevoked)).toBeTruthy();
    const request = apiFetch.mock.calls.find(([url, options]) => url.endsWith("/credentials/revoke") && options?.method === "POST");
    expect(JSON.parse(request[1].body)).toEqual({ expected_revision: 7 });
    expect(await screen.findByText(uiText.en.sourceCredential_revoked)).toBeTruthy();
    expect(screen.getByRole("checkbox").disabled).toBe(true);
  });
});
