import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import NotificationPermissionPrompt from "./NotificationPermissionPrompt";
import {
  enableBrowserPushNotifications,
  getBrowserPushStatus,
  getPushPublicKey,
} from "../services/notificationsApi";

vi.mock("../services/notificationsApi", () => ({
  enableBrowserPushNotifications: vi.fn(),
  getBrowserPushStatus: vi.fn(),
  getPushPublicKey: vi.fn(),
}));

const user = { id: 17, tenant_id: 9, email: "owner@example.com" };

beforeEach(() => {
  sessionStorage.clear();
  getBrowserPushStatus.mockResolvedValue({ enabled: false, reason: "" });
  getPushPublicKey.mockResolvedValue({ enabled: true, public_key: "public-key" });
  enableBrowserPushNotifications.mockResolvedValue({ enabled: true });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("NotificationPermissionPrompt", () => {
  it("offers device push enrollment and enables it from the user click", async () => {
    render(<NotificationPermissionPrompt user={user} lang="en" />);

    expect(await screen.findByRole("dialog")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Enable notifications" }));

    await waitFor(() => expect(enableBrowserPushNotifications).toHaveBeenCalledWith({
      tenantId: 9,
      pushConfig: { enabled: true, public_key: "public-key" },
    }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("does not prompt when this browser is already subscribed", async () => {
    getBrowserPushStatus.mockResolvedValueOnce({ enabled: true });
    render(<NotificationPermissionPrompt user={user} lang="en" />);

    await waitFor(() => expect(getBrowserPushStatus).toHaveBeenCalled());
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(getPushPublicKey).not.toHaveBeenCalled();
  });

  it("remembers Not now for the current browser session", async () => {
    const first = render(<NotificationPermissionPrompt user={user} lang="en" />);
    fireEvent.click(await screen.findByRole("button", { name: "Not now" }));
    first.unmount();

    render(<NotificationPermissionPrompt user={user} lang="en" />);
    await Promise.resolve();

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(getBrowserPushStatus).toHaveBeenCalledTimes(1);
  });

  it("shows browser-settings guidance without retrying a blocked permission", async () => {
    getBrowserPushStatus.mockResolvedValueOnce({ enabled: false, reason: "permission_denied" });
    render(<NotificationPermissionPrompt user={user} lang="en" />);

    expect(await screen.findByText("Notifications are blocked")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Enable notifications" })).toBeNull();
    expect(getPushPublicKey).not.toHaveBeenCalled();
  });

  it("focuses the primary action, dismisses with Escape, and restores focus", async () => {
    const launcher = document.createElement("button");
    launcher.textContent = "Open account";
    document.body.appendChild(launcher);
    launcher.focus();

    render(<NotificationPermissionPrompt user={user} lang="en" />);

    const primaryAction = await screen.findByRole("button", { name: "Enable notifications" });
    await waitFor(() => expect(document.activeElement).toBe(primaryAction));
    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(launcher);
    launcher.remove();
  });

  it("preserves the Arabic direction and localized close-button name", async () => {
    render(<NotificationPermissionPrompt user={user} lang="ar" />);

    const dialog = await screen.findByRole("dialog");
    expect(dialog.parentElement?.getAttribute("dir")).toBe("rtl");
    fireEvent.click(screen.getByRole("button", { name: "إغلاق نافذة الإشعارات" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });
});
