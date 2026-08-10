import { beforeEach, describe, expect, it, vi } from "vitest";

const { apiFetch } = vi.hoisted(() => ({ apiFetch: vi.fn() }));

vi.mock("../utils/apiClient", () => ({
  apiFetch,
  getApiUrl: (path) => path,
  readApiError: (_data, fallback) => fallback,
  readApiResponse: async (response) => response.data,
}));

import {
  getInstallationContext,
  getInstallationId,
  MADAR_INSTALLATION_STORAGE_KEY,
  registerInstallation,
  resetInstallationRegistrationForTests,
} from "./installation";

const UUID = "123e4567-e89b-42d3-a456-426614174000";
const appLocation = { hostname: "app.madarportal.com" };

describe("Madar installation identity", () => {
  beforeEach(() => {
    apiFetch.mockReset().mockResolvedValue({
      ok: true,
      data: { success: true, installation: { installation_id: UUID } },
    });
    localStorage.clear();
    resetInstallationRegistrationForTests();
  });

  it("creates one opaque UUID and persists it across helper calls", () => {
    const cryptoLike = { randomUUID: vi.fn(() => UUID) };
    expect(getInstallationId({ storage: localStorage, cryptoLike, locationLike: appLocation })).toBe(UUID);
    expect(getInstallationId({ storage: localStorage, cryptoLike, locationLike: appLocation })).toBe(UUID);
    expect(cryptoLike.randomUUID).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem(MADAR_INSTALLATION_STORAGE_KEY)).toBe(UUID);
  });

  it("uses a stable in-page fallback when storage is unavailable", () => {
    const storage = { getItem: vi.fn(() => { throw new Error("blocked"); }), setItem: vi.fn(() => { throw new Error("blocked"); }) };
    const cryptoLike = { randomUUID: vi.fn(() => UUID) };
    expect(getInstallationId({ storage, cryptoLike, locationLike: appLocation })).toBe(UUID);
    expect(getInstallationId({ storage, cryptoLike, locationLike: appLocation })).toBe(UUID);
    expect(cryptoLike.randomUUID).toHaveBeenCalledTimes(1);
  });

  it("does not create or register identity on customer hosts", async () => {
    const cryptoLike = { randomUUID: vi.fn(() => UUID) };
    expect(getInstallationId({ storage: localStorage, cryptoLike, locationLike: { hostname: "customer.madarportal.com" } })).toBeNull();
    await expect(registerInstallation({ tenantId: 9, windowLike: { location: { hostname: "customer.madarportal.com" } } })).resolves.toBeNull();
    expect(cryptoLike.randomUUID).not.toHaveBeenCalled();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("reports standalone and iOS standalone without requesting permission", () => {
    const requestPermission = vi.fn();
    const context = getInstallationContext({
      location: appLocation,
      matchMedia: () => ({ matches: false }),
      navigator: { standalone: true, platform: "iPhone" },
      Notification: { permission: "default", requestPermission },
    });
    expect(context).toMatchObject({ displayMode: "ios_standalone", platform: "ios", installedConfirmed: true });
    expect(requestPermission).not.toHaveBeenCalled();
  });

  it("registers once per tenant/context and reconciles tenant transitions", async () => {
    const windowLike = {
      location: appLocation,
      localStorage,
      crypto: { randomUUID: () => UUID },
      matchMedia: () => ({ matches: false }),
      navigator: { platform: "Linux" },
      Notification: { permission: "default", requestPermission: vi.fn() },
    };
    await registerInstallation({ tenantId: 1, windowLike });
    await registerInstallation({ tenantId: 1, windowLike });
    await registerInstallation({ tenantId: 2, windowLike });
    expect(apiFetch).toHaveBeenCalledTimes(2);
    expect(windowLike.Notification.requestPermission).not.toHaveBeenCalled();
    expect(JSON.parse(apiFetch.mock.calls[1][1].body)).not.toHaveProperty("tenant_id");
  });

  it("makes standalone confirmation monotonic through registration signals", async () => {
    const windowLike = {
      location: appLocation, localStorage, crypto: { randomUUID: () => UUID },
      matchMedia: () => ({ matches: false }), navigator: {}, Notification: { permission: "granted" },
    };
    await registerInstallation({ tenantId: 1, installedConfirmed: true, windowLike });
    expect(JSON.parse(apiFetch.mock.calls[0][1].body).installed_confirmed).toBe(true);
  });
});
