import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import NotificationBell from "./NotificationBell";
import {
  fetchNotifications,
  reconcileBrowserPushSubscription,
} from "../../services/notificationsApi";

vi.mock("../../services/notificationsApi", () => ({
  fetchNotifications: vi.fn(),
  reconcileBrowserPushSubscription: vi.fn(),
}));

const translate = (key, values = {}) => {
  if (key === "notifications.title") return "Notifications";
  if (key === "notifications.unreadCount") return `${values.count} unread`;
  if (key === "notifications.viewAll") return "View all";
  if (key === "notifications.ariaRecent") return "Recent notifications";
  return key;
};

vi.mock("../../i18n", () => ({
  useLanguage: () => ({ t: translate }),
}));

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, reject, resolve };
};

const response = (id, title, unreadCount = 1) => ({
  notifications: [{ id, title, body: `${title} detail`, unread: true }],
  unread_count: unreadCount,
});

const renderBell = (props) => render(
  <MemoryRouter>
    <NotificationBell tenantId={props.tenantId} userId="7" />
  </MemoryRouter>,
);

describe("NotificationBell tenant safety", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    fetchNotifications.mockReset();
    reconcileBrowserPushSubscription.mockReset();
    reconcileBrowserPushSubscription.mockResolvedValue({ reconciled: false });
  });

  it("clears tenant state immediately and ignores a late prior-tenant response", async () => {
    const tenantB = deferred();
    fetchNotifications
      .mockResolvedValueOnce(response("a", "Tenant A notification", 3))
      .mockImplementationOnce(() => tenantB.promise);

    const view = renderBell({ tenantId: "tenant-a" });
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));
    expect(await screen.findByText("Tenant A notification")).toBeTruthy();
    expect(screen.getByText("3")).toBeTruthy();

    view.rerender(
      <MemoryRouter>
        <NotificationBell tenantId="tenant-b" userId="7" />
      </MemoryRouter>,
    );

    expect(reconcileBrowserPushSubscription).toHaveBeenCalledTimes(2);
    expect(screen.queryByText("Tenant A notification")).toBeNull();
    expect(screen.queryByText("3")).toBeNull();

    tenantB.resolve(response("b", "Tenant B notification", 1));
    expect(await screen.findByText("Tenant B notification")).toBeTruthy();
  });

  it("does not let a late tenant A response overwrite tenant B", async () => {
    const tenantA = deferred();
    const tenantB = deferred();
    fetchNotifications
      .mockImplementationOnce(() => tenantA.promise)
      .mockImplementationOnce(() => tenantB.promise);

    const view = renderBell({ tenantId: "tenant-a" });
    view.rerender(
      <MemoryRouter>
        <NotificationBell tenantId="tenant-b" userId="7" />
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));

    tenantB.resolve(response("b", "Tenant B notification"));
    expect(await screen.findByText("Tenant B notification")).toBeTruthy();
    tenantA.resolve(response("a", "Tenant A notification"));
    await waitFor(() => expect(screen.queryByText("Tenant A notification")).toBeNull());
    expect(screen.getByText("Tenant B notification")).toBeTruthy();
  });

  it("shows no fabricated notification or unread badge on API failure", async () => {
    fetchNotifications.mockRejectedValueOnce(new Error("offline"));
    renderBell({ tenantId: "tenant-a" });
    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));

    await waitFor(() => expect(fetchNotifications).toHaveBeenCalledTimes(1));
    expect(screen.queryByText("New form submission")).toBeNull();
    expect(document.querySelector(".notification-bell-badge")).toBeNull();
  });

  it("keeps focus polling and prevents overlapping requests", async () => {
    const initial = deferred();
    fetchNotifications.mockImplementationOnce(() => initial.promise).mockResolvedValue(response("next", "Next"));
    renderBell({ tenantId: "tenant-a" });
    expect(fetchNotifications).toHaveBeenCalledTimes(1);
    fireEvent.focus(window);
    fireEvent.focus(window);
    expect(fetchNotifications).toHaveBeenCalledTimes(1);
    initial.resolve(response("a", "First"));
    await waitFor(() => expect(document.querySelector(".notification-bell-badge")).toBeTruthy());
    fireEvent.focus(window);
    await waitFor(() => expect(fetchNotifications).toHaveBeenCalledTimes(2));
  });
});
