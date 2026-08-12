import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const {
  disableCurrentInstallationNotifications,
  enableBrowserPushNotifications,
  getMadarServiceWorkerRegistration,
  getPushPublicKey,
  listInstallations,
  registerInstallation,
  revokeInstallation,
} = vi.hoisted(() => ({
  disableCurrentInstallationNotifications: vi.fn(),
  enableBrowserPushNotifications: vi.fn(),
  getMadarServiceWorkerRegistration: vi.fn(),
  getPushPublicKey: vi.fn(),
  listInstallations: vi.fn(),
  registerInstallation: vi.fn(),
  revokeInstallation: vi.fn(),
}));

vi.mock("../../services/installationsApi", () => ({
  disableCurrentInstallationNotifications,
  listInstallations,
  revokeInstallation,
}));
vi.mock("../../services/notificationsApi", () => ({
  enableBrowserPushNotifications,
  getPushPublicKey,
}));
vi.mock("../../pwa/serviceWorker", () => ({ getMadarServiceWorkerRegistration }));
vi.mock("../../pwa/installation", async (importOriginal) => ({
  ...(await importOriginal()),
  getInstallationId: ({ locationLike = globalThis.location } = {}) =>
    String(locationLike?.hostname || "").startsWith("customer.")
      ? null
      : "123e4567-e89b-42d3-a456-426614174000",
  registerInstallation,
}));

import { getSettingsContent } from "../../content";
import DeviceSettingsPanel from "./DeviceSettingsPanel";

const copy = getSettingsContent("en").devices;
const current = {
  id: "223e4567-e89b-42d3-a456-426614174000",
  platform: "linux",
  display_mode: "browser",
  notification_permission: "granted",
  notifications_enabled: true,
  has_active_push_subscription: true,
  last_seen_at: "2026-08-11T10:00:00Z",
  is_current: true,
};
const remote = {
  id: "323e4567-e89b-42d3-a456-426614174000",
  platform: "android",
  display_mode: "standalone",
  notification_permission: "default",
  notifications_enabled: false,
  has_active_push_subscription: false,
  last_seen_at: "2026-08-10T10:00:00Z",
  is_current: false,
};

function renderPanel(props = {}) {
  return render(
    <DeviceSettingsPanel
      lang="en"
      tenantId={9}
      copy={copy}
      showNotification={vi.fn()}
      {...props}
    />
  );
}

describe("DeviceSettingsPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listInstallations.mockResolvedValue([remote, current]);
    revokeInstallation.mockResolvedValue({ success: true });
    disableCurrentInstallationNotifications.mockResolvedValue({ success: true });
    enableBrowserPushNotifications.mockResolvedValue({ enabled: true });
    getPushPublicKey.mockResolvedValue({ enabled: true, public_key: "AQID" });
    getMadarServiceWorkerRegistration.mockResolvedValue({
      pushManager: { getSubscription: vi.fn().mockResolvedValue(null) },
    });
    registerInstallation.mockResolvedValue({ success: true });
    Object.defineProperty(window, "Notification", {
      configurable: true,
      value: { permission: "granted", requestPermission: vi.fn() },
    });
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({ matches: false })),
    });
    Object.defineProperty(navigator, "standalone", { configurable: true, value: false });
    Object.defineProperty(navigator, "platform", { configurable: true, value: "Linux" });
    Object.defineProperty(navigator, "userAgent", { configurable: true, value: "Mozilla/5.0 (X11; Linux x86_64)" });
  });

  afterEach(cleanup);

  it("shows the current device first with coarse labels and no internal IDs", async () => {
    renderPanel();
    await screen.findByText("Current device");
    const articles = document.querySelectorAll(".device-settings-item");
    expect(articles[0].textContent).toContain("Linux");
    expect(articles[0].textContent).toContain("Notifications enabled");
    expect(articles[1].textContent).toContain("Android");
    expect(articles[1].textContent).toContain("Installed app");
    expect(screen.queryByText(current.id)).toBeNull();
    expect(screen.getAllByRole("button", { name: "Remove device" })).toHaveLength(1);
  });

  it("confirms and removes only the selected remote device", async () => {
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Remove device" }));
    expect(screen.getByRole("dialog").textContent).toContain("does not sign that browser out");
    fireEvent.click(screen.getByRole("dialog").querySelector(".page-delete-modal-danger"));
    await waitFor(() => expect(revokeInstallation).toHaveBeenCalledWith(remote.id));
    await waitFor(() => expect(screen.queryByText("Android")).toBeNull());
    expect(screen.getByText("Current device")).toBeTruthy();
  });

  it("disables only the current device and unsubscribes locally", async () => {
    const unsubscribe = vi.fn().mockResolvedValue(true);
    getMadarServiceWorkerRegistration.mockResolvedValue({
      pushManager: { getSubscription: vi.fn().mockResolvedValue({ unsubscribe }) },
    });
    listInstallations
      .mockResolvedValueOnce([current, remote])
      .mockResolvedValueOnce([{ ...current, notifications_enabled: false, has_active_push_subscription: false }, remote]);
    renderPanel();
    fireEvent.click(await screen.findByRole("button", { name: "Disable notifications" }));
    await waitFor(() => expect(disableCurrentInstallationNotifications).toHaveBeenCalled());
    expect(unsubscribe).toHaveBeenCalledTimes(1);
  });

  it("does not prompt on mount and invokes deferred install only after a click", async () => {
    renderPanel();
    const prompt = vi.fn().mockResolvedValue(undefined);
    const event = new Event("beforeinstallprompt");
    Object.defineProperty(event, "prompt", { value: prompt });
    Object.defineProperty(event, "userChoice", { value: Promise.resolve({ outcome: "accepted" }) });
    fireEvent(window, event);
    const installButton = await screen.findByRole("button", { name: "Install Madar" });
    expect(prompt).not.toHaveBeenCalled();
    fireEvent.click(installButton);
    await waitFor(() => expect(prompt).toHaveBeenCalledTimes(1));
  });

  it("shows installed state in standalone mode and no install button", async () => {
    window.matchMedia.mockReturnValue({ matches: true });
    renderPanel();
    expect(await screen.findByText(/running as an installed app/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Install Madar" })).toBeNull();
  });

  it("shows iOS Add to Home Screen guidance without a Chromium button", async () => {
    Object.defineProperty(navigator, "userAgent", { configurable: true, value: "Mozilla/5.0 (iPhone)" });
    Object.defineProperty(navigator, "platform", { configurable: true, value: "iPhone" });
    renderPanel();
    expect(await screen.findByText(/Share menu.*Add to Home Screen/i)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Install Madar" })).toBeNull();
  });

  it("shows blocked state without requesting permission on mount", async () => {
    window.Notification.permission = "denied";
    renderPanel();
    expect(await screen.findByText("Notifications blocked")).toBeTruthy();
    expect(window.Notification.requestPermission).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Enable notifications" })).toBeNull();
  });

  it("does not render or request device state on a customer host", async () => {
    const originalLocation = window.location;
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { hostname: "customer.madarportal.com" },
    });
    renderPanel();
    expect(screen.queryByText("Devices")).toBeNull();
    expect(listInstallations).not.toHaveBeenCalled();
    expect(getPushPublicKey).not.toHaveBeenCalled();
    Object.defineProperty(window, "location", { configurable: true, value: originalLocation });
  });
});
