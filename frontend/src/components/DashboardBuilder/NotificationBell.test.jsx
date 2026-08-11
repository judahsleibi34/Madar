import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import NotificationBell from "./NotificationBell";
import { NotificationProvider } from "../../notifications/NotificationProvider";
import { fetchNotifications } from "../../services/notificationsApi";

vi.mock("../../services/notificationsApi", () => ({
  fetchNotifications: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  markNotificationRead: vi.fn(),
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
    <NotificationProvider
      user={{ id: "7", tenant_id: props.tenantId }}
      pollIntervalMs={0}
      claimToast={vi.fn().mockResolvedValue(true)}
    >
      <NotificationBell />
    </NotificationProvider>
  </MemoryRouter>,
);

const CurrentPath = () => {
  const location = useLocation();
  return <output data-testid="current-path">{location.pathname}</output>;
};

describe("NotificationBell tenant safety", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    fetchNotifications.mockReset();
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
        <NotificationProvider
          user={{ id: "7", tenant_id: "tenant-b" }}
          pollIntervalMs={0}
          claimToast={vi.fn().mockResolvedValue(true)}
        >
          <NotificationBell />
        </NotificationProvider>
      </MemoryRouter>,
    );

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
        <NotificationProvider
          user={{ id: "7", tenant_id: "tenant-b" }}
          pollIntervalMs={0}
          claimToast={vi.fn().mockResolvedValue(true)}
        >
          <NotificationBell />
        </NotificationProvider>
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

  it("opens the notifications page directly and closes the mobile drawer", async () => {
    const onNavigate = vi.fn();
    fetchNotifications.mockResolvedValueOnce(response("a", "Mobile notification"));
    vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true })));

    render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <NotificationProvider
          user={{ id: "7", tenant_id: "tenant-a" }}
          pollIntervalMs={0}
          claimToast={vi.fn().mockResolvedValue(true)}
        >
          <NotificationBell onNavigate={onNavigate} />
          <CurrentPath />
        </NotificationProvider>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Notifications" }));

    expect(screen.getByTestId("current-path").textContent).toBe("/notifications");
    expect(onNavigate).toHaveBeenCalledOnce();
    expect(screen.queryByRole("dialog")).toBeNull();
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
