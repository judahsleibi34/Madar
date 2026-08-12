import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  NotificationProvider,
} from "./NotificationProvider";
import { useNotifications } from "./NotificationContext";
import { notificationProviderConstants } from "./notificationState";
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "../services/notificationsApi";

vi.mock("../services/notificationsApi", () => ({
  fetchNotifications: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  markNotificationRead: vi.fn(),
}));

const userA = { id: "user-1", tenant_id: "tenant-a" };
const userB = { id: "user-1", tenant_id: "tenant-b" };

const item = (id, createdAt, options = {}) => ({
  id,
  title: options.title || `Notification ${id}`,
  body: options.body || `Detail ${id}`,
  created_at: createdAt,
  unread: options.unread !== false,
  read_at: options.unread === false ? createdAt : null,
  data: options.data || { action: { kind: "notification_center", path: "/notifications" } },
});

const response = (notifications, unreadCount = notifications.filter((entry) => entry.unread !== false).length) => ({
  notifications,
  unread_count: unreadCount,
});

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, reject, resolve };
};

function Harness() {
  const state = useNotifications();
  return (
    <div>
      <output data-testid="ids">{state.notifications.map((entry) => entry.id).join(",")}</output>
      <output data-testid="unread">{state.unreadCount}</output>
      <output data-testid="toasts">{state.toastQueue.map((entry) => entry.id).join(",")}</output>
      <output data-testid="loading">{String(state.loading)}</output>
      <output data-testid="error">{state.error ? "error" : "ok"}</output>
      <button type="button" onClick={state.refreshNotifications}>Refresh</button>
      <button type="button" onClick={() => state.markRead("d")}>Read D</button>
      <button type="button" onClick={state.markAllRead}>Read all</button>
      {state.toastQueue.map((entry) => (
        <button type="button" key={entry.key} onClick={() => state.dismissToast(entry.key)}>
          Dismiss {entry.id}
        </button>
      ))}
    </div>
  );
}

const renderProvider = (user = userA, options = {}) => render(
  <NotificationProvider
    user={user}
    pollIntervalMs={0}
    claimToast={options.claimToast || vi.fn().mockResolvedValue(true)}
  >
    <Harness />
  </NotificationProvider>,
);

describe("NotificationProvider", () => {
  afterEach(cleanup);

  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    fetchNotifications.mockReset();
    markNotificationRead.mockReset().mockResolvedValue({ success: true });
    markAllNotificationsRead.mockReset().mockResolvedValue({ success: true });
  });

  it("uses the first successful fetch as a no-toast baseline, including unread backlog", async () => {
    fetchNotifications.mockResolvedValueOnce(response([
      item("c", "2026-08-11T10:03:00Z"),
      item("b", "2026-08-11T10:02:00Z"),
      item("a", "2026-08-11T10:01:00Z"),
    ], 27));
    renderProvider();

    await waitFor(() => expect(screen.getByTestId("ids").textContent).toBe("c,b,a"));
    expect(screen.getByTestId("unread").textContent).toBe("27");
    expect(screen.getByTestId("toasts").textContent).toBe("");
    expect(fetchNotifications).toHaveBeenCalledWith(expect.objectContaining({ limit: 50 }));
  });

  it("toasts only newly observed records in chronological order", async () => {
    fetchNotifications
      .mockResolvedValueOnce(response([item("a", "2026-08-11T10:00:00Z")]))
      .mockResolvedValueOnce(response([
        item("d", "2026-08-11T10:03:00Z"),
        item("c", "2026-08-11T10:02:00Z"),
        item("b", "2026-08-11T10:01:00Z"),
        item("a", "2026-08-11T10:00:00Z"),
      ]));
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("ids").textContent).toBe("a"));
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

    await waitFor(() => expect(screen.getByTestId("toasts").textContent).toBe("b,c,d"));
    expect(screen.getByTestId("ids").textContent).toBe("d,c,b,a");
  });

  it("keeps an initial failure unbaselined so recovery backlog does not toast", async () => {
    fetchNotifications
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(response([item("old", "2026-08-10T10:00:00Z")]));
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("error").textContent).toBe("error"));
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(screen.getByTestId("ids").textContent).toBe("old"));
    expect(screen.getByTestId("toasts").textContent).toBe("");
  });

  it("toasts notifications discovered after an established outage", async () => {
    fetchNotifications
      .mockResolvedValueOnce(response([item("a", "2026-08-11T10:00:00Z")]))
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(response([
        item("c", "2026-08-11T10:02:00Z"),
        item("b", "2026-08-11T10:01:00Z"),
        item("a", "2026-08-11T10:00:00Z"),
      ]));
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("ids").textContent).toBe("a"));
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(screen.getByTestId("error").textContent).toBe("error"));
    expect(screen.getByTestId("ids").textContent).toBe("a");
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(screen.getByTestId("toasts").textContent).toBe("b,c"));
  });

  it("clears tenant A immediately, baselines B, and ignores a late A response", async () => {
    const tenantA = deferred();
    const tenantB = deferred();
    fetchNotifications
      .mockImplementationOnce(() => tenantA.promise)
      .mockImplementationOnce(() => tenantB.promise)
      .mockResolvedValueOnce(response([
        item("b-new", "2026-08-11T11:00:00Z"),
        item("b-base", "2026-08-11T10:00:00Z"),
      ]));
    const view = renderProvider(userA);
    view.rerender(
      <NotificationProvider user={userB} pollIntervalMs={0} claimToast={vi.fn().mockResolvedValue(true)}>
        <Harness />
      </NotificationProvider>,
    );
    expect(screen.getByTestId("ids").textContent).toBe("");
    expect(screen.getByTestId("unread").textContent).toBe("0");
    expect(screen.getByTestId("toasts").textContent).toBe("");

    tenantB.resolve(response([item("b-base", "2026-08-11T10:00:00Z")], 1));
    await waitFor(() => expect(screen.getByTestId("ids").textContent).toBe("b-base"));
    expect(screen.getByTestId("toasts").textContent).toBe("");
    tenantA.resolve(response([item("a-late", "2026-08-11T12:00:00Z")], 8));
    await Promise.resolve();
    expect(screen.getByTestId("ids").textContent).toBe("b-base");

    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(screen.getByTestId("toasts").textContent).toBe("b-new"));
  });

  it("clears state when identity disappears and establishes a fresh user baseline", async () => {
    fetchNotifications
      .mockResolvedValueOnce(response([item("a", "2026-08-11T10:00:00Z")], 1))
      .mockResolvedValueOnce(response([item("other", "2026-08-11T11:00:00Z")], 1));
    const claimToast = vi.fn().mockResolvedValue(true);
    const view = renderProvider(userA, { claimToast });
    await waitFor(() => expect(screen.getByTestId("ids").textContent).toBe("a"));
    view.rerender(
      <NotificationProvider user={null} pollIntervalMs={0} claimToast={claimToast}>
        <Harness />
      </NotificationProvider>,
    );
    expect(screen.getByTestId("ids").textContent).toBe("");
    view.rerender(
      <NotificationProvider user={{ id: "user-2", tenant_id: "tenant-a" }} pollIntervalMs={0} claimToast={claimToast}>
        <Harness />
      </NotificationProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("ids").textContent).toBe("other"));
    expect(screen.getByTestId("toasts").textContent).toBe("");
  });

  it("updates read state only after API success and toast display/dismissal does not mark read", async () => {
    fetchNotifications
      .mockResolvedValueOnce(response([item("a", "2026-08-11T10:00:00Z")]))
      .mockResolvedValueOnce(response([
        item("d", "2026-08-11T10:01:00Z"),
        item("a", "2026-08-11T10:00:00Z"),
      ], 2));
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("ids").textContent).toBe("a"));
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Dismiss d" })).toBeTruthy());
    expect(markNotificationRead).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss d" }));
    expect(screen.getByTestId("unread").textContent).toBe("2");
    fireEvent.click(screen.getByRole("button", { name: "Read D" }));
    await waitFor(() => expect(screen.getByTestId("unread").textContent).toBe("1"));
    fireEvent.click(screen.getByRole("button", { name: "Read all" }));
    await waitFor(() => expect(screen.getByTestId("unread").textContent).toBe("0"));
  });

  it("bounds the transient queue while retaining all fetched history", async () => {
    const burst = Array.from({ length: notificationProviderConstants.MAX_TOAST_QUEUE + 5 }, (_, index) => (
      item(`new-${index}`, `2026-08-11T10:${String(index).padStart(2, "0")}:00Z`)
    ));
    fetchNotifications
      .mockResolvedValueOnce(response([item("base", "2026-08-11T09:00:00Z")]))
      .mockResolvedValueOnce(response([...burst, item("base", "2026-08-11T09:00:00Z")]));
    renderProvider();
    await waitFor(() => expect(screen.getByTestId("ids").textContent).toBe("base"));
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => {
      const toastIds = screen.getByTestId("toasts").textContent.split(",").filter(Boolean);
      expect(toastIds).toHaveLength(notificationProviderConstants.MAX_TOAST_QUEUE);
    });
    expect(screen.getByTestId("ids").textContent.split(",")).toHaveLength(burst.length + 1);
  });

  it("prevents overlapping focus refreshes", async () => {
    const initial = deferred();
    fetchNotifications.mockImplementationOnce(() => initial.promise).mockResolvedValue(response([]));
    renderProvider();
    fireEvent.focus(window);
    fireEvent.focus(window);
    expect(fetchNotifications).toHaveBeenCalledTimes(1);
    initial.resolve(response([]));
    await waitFor(() => expect(screen.getByTestId("loading").textContent).toBe("false"));
    fireEvent.focus(window);
    await waitFor(() => expect(fetchNotifications).toHaveBeenCalledTimes(2));
  });
});
