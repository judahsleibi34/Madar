import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import NotificationsPage from "./NotificationsPage";
import {
  fetchNotifications,
  getBrowserPushStatus,
} from "../../services/notificationsApi";

vi.mock("../../services/notificationsApi", () => ({
  enableBrowserPushNotifications: vi.fn(),
  fetchNotifications: vi.fn(),
  getBrowserPushStatus: vi.fn(),
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

describe("NotificationsPage tenant safety", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    fetchNotifications.mockReset();
    getBrowserPushStatus.mockReset();
    getBrowserPushStatus.mockResolvedValue({ enabled: false, reason: "" });
  });

  it("restores the enabled Push state after a page refresh", async () => {
    getBrowserPushStatus.mockResolvedValue({ enabled: true });
    fetchNotifications.mockResolvedValue(response("a", "Notification"));
    render(<NotificationsPage user={{ id: 7, tenant_id: "tenant-a" }} />);
    expect((await screen.findByRole("button", { name: "Push enabled" })).disabled).toBe(true);
    expect(screen.getByText("Push is enabled")).toBeTruthy();
  });

  it("clears old tenant content while loading the next tenant", async () => {
    const tenantB = deferred();
    fetchNotifications.mockResolvedValueOnce(response("a", "Tenant A notification", 2)).mockImplementationOnce(() => tenantB.promise);
    const view = render(<NotificationsPage user={{ id: 7, tenant_id: "tenant-a" }} />);
    expect(await screen.findByText("Tenant A notification")).toBeTruthy();

    view.rerender(<NotificationsPage user={{ id: 7, tenant_id: "tenant-b" }} />);
    expect(screen.queryByText("Tenant A notification")).toBeNull();
    expect(screen.queryByText("2", { selector: ".notifications-header-count strong" })).toBeNull();

    tenantB.resolve(response("b", "Tenant B notification"));
    expect(await screen.findByText("Tenant B notification")).toBeTruthy();
  });

  it("ignores a stale response and never renders dummy data on failure", async () => {
    const tenantA = deferred();
    fetchNotifications.mockImplementationOnce(() => tenantA.promise).mockRejectedValueOnce(new Error("offline"));
    const view = render(<NotificationsPage user={{ id: 7, tenant_id: "tenant-a" }} />);
    view.rerender(<NotificationsPage user={{ id: 7, tenant_id: "tenant-b" }} />);

    expect(await screen.findByText("No notifications")).toBeTruthy();
    tenantA.resolve(response("a", "Tenant A notification", 4));
    await waitFor(() => expect(screen.queryByText("Tenant A notification")).toBeNull());
    expect(screen.queryByText("New form submission")).toBeNull();
    expect(screen.getByText("0", { selector: ".notifications-header-count strong" })).toBeTruthy();
  });
});
