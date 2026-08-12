import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import NotificationsPage from "./NotificationsPage";
import { NotificationProvider } from "../../notifications/NotificationProvider";
import {
  fetchNotifications,
  getBrowserPushStatus,
  getPushPublicKey,
  markAllNotificationsRead,
  markNotificationRead,
} from "../../services/notificationsApi";

vi.mock("../../services/notificationsApi", () => ({
  enableBrowserPushNotifications: vi.fn(),
  fetchNotifications: vi.fn(),
  getBrowserPushStatus: vi.fn(),
  getPushPublicKey: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  markNotificationRead: vi.fn(),
}));

const translate = (key, values = {}) => {
  const labels = {
    "notifications.title": "Notifications",
    "notifications.fallbackTitle": "Notification",
    "notifications.emptyTitle": "No notifications",
    "notifications.emptyDetail": "Nothing to show.",
    "notifications.total": "Total",
    "notifications.unread": "Unread",
    "notifications.sources": "Sources",
    "notifications.markAllRead": "Mark all read",
    "notifications.enablePush": "Enable push",
    "notifications.pushEnabledButton": "Push enabled",
    "notifications.pushState.enabled": "Push is enabled",
  };
  if (key === "notifications.unreadCount") return `${values.count} unread`;
  if (key === "notifications.items") return `${values.count} items`;
  return labels[key] || key;
};

vi.mock("../../i18n", () => ({
  useLanguage: () => ({ direction: "ltr", t: translate }),
}));

const deferred = () => {
  let resolve;
  const promise = new Promise((onResolve) => { resolve = onResolve; });
  return { promise, resolve };
};

const response = (id, title, unreadCount = 1) => ({
  notifications: [{ id, title, body: `${title} detail`, unread: true }],
  unread_count: unreadCount,
});

const renderPage = (user) => render(
  <NotificationProvider
    user={user}
    pollIntervalMs={0}
    claimToast={vi.fn().mockResolvedValue(true)}
  >
    <NotificationsPage user={user} />
  </NotificationProvider>,
);

describe("NotificationsPage tenant safety", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    fetchNotifications.mockReset();
    getBrowserPushStatus.mockReset();
    getBrowserPushStatus.mockResolvedValue({ enabled: false, reason: "" });
    getPushPublicKey.mockReset();
    getPushPublicKey.mockResolvedValue({ enabled: true, public_key: "AQID" });
    markNotificationRead.mockReset().mockResolvedValue({ success: true });
    markAllNotificationsRead.mockReset().mockResolvedValue({ success: true });
  });

  it("restores the enabled Push state after a page refresh", async () => {
    getBrowserPushStatus.mockResolvedValue({ enabled: true });
    fetchNotifications.mockResolvedValue(response("a", "Notification"));
    renderPage({ id: 7, tenant_id: "tenant-a" });
    expect((await screen.findByRole("button", { name: "Push enabled" })).disabled).toBe(true);
    expect(screen.getByText("Push is enabled")).toBeTruthy();
  });

  it("shows server unavailability without leaving an active permission button", async () => {
    getPushPublicKey.mockResolvedValue({ enabled: false, public_key: "" });
    fetchNotifications.mockResolvedValue(response("a", "Notification"));
    renderPage({ id: 7, tenant_id: "tenant-a" });

    const button = await screen.findByRole("button", { name: "Enable push" });
    expect(button.disabled).toBe(true);
  });

  it("clears old tenant content while loading the next tenant", async () => {
    const tenantBResponse = deferred();
    fetchNotifications.mockResolvedValueOnce(response("a", "Tenant A notification", 2)).mockImplementationOnce(() => tenantBResponse.promise);
    const view = renderPage({ id: 7, tenant_id: "tenant-a" });
    expect(await screen.findByText("Tenant A notification")).toBeTruthy();

    const tenantB = { id: 7, tenant_id: "tenant-b" };
    view.rerender(
      <NotificationProvider
        user={tenantB}
        pollIntervalMs={0}
        claimToast={vi.fn().mockResolvedValue(true)}
      >
        <NotificationsPage user={tenantB} />
      </NotificationProvider>,
    );
    expect(screen.queryByText("Tenant A notification")).toBeNull();
    expect(screen.queryByText("2", { selector: ".notifications-header-count strong" })).toBeNull();

    tenantBResponse.resolve(response("b", "Tenant B notification"));
    expect(await screen.findByText("Tenant B notification")).toBeTruthy();
  });

  it("ignores a stale response and never renders dummy data on failure", async () => {
    const tenantA = deferred();
    fetchNotifications.mockImplementationOnce(() => tenantA.promise).mockRejectedValueOnce(new Error("offline"));
    const view = renderPage({ id: 7, tenant_id: "tenant-a" });
    const tenantB = { id: 7, tenant_id: "tenant-b" };
    view.rerender(
      <NotificationProvider
        user={tenantB}
        pollIntervalMs={0}
        claimToast={vi.fn().mockResolvedValue(true)}
      >
        <NotificationsPage user={tenantB} />
      </NotificationProvider>,
    );

    expect(await screen.findByText("No notifications")).toBeTruthy();
    tenantA.resolve(response("a", "Tenant A notification", 4));
    await waitFor(() => expect(screen.queryByText("Tenant A notification")).toBeNull());
    expect(screen.queryByText("New form submission")).toBeNull();
    expect(screen.getByText("0", { selector: ".notifications-header-count strong" })).toBeTruthy();
  });

  it("uses shared read operations and reconciles the unread count once", async () => {
    fetchNotifications.mockResolvedValueOnce(response("a", "Notification", 1));
    renderPage({ id: 7, tenant_id: "tenant-a" });
    const notificationRow = await screen.findByText("Notification");

    fireEvent.click(notificationRow.closest("article"));
    await waitFor(() => expect(markNotificationRead).toHaveBeenCalledWith("a"));
    expect(screen.getByText("0", { selector: ".notifications-header-count strong" })).toBeTruthy();

    fetchNotifications.mockResolvedValueOnce(response("b", "Another", 2));
    fireEvent.focus(window);
    await screen.findByText("Another");
    fireEvent.click(screen.getByRole("button", { name: "Mark all read" }));
    await waitFor(() => expect(markAllNotificationsRead).toHaveBeenCalledOnce());
    expect(screen.getByText("0", { selector: ".notifications-header-count strong" })).toBeTruthy();
  });
});
