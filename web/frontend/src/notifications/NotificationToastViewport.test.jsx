import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NotificationProvider } from "./NotificationProvider";
import { useNotifications } from "./NotificationContext";
import NotificationToastViewport, { MAX_VISIBLE_TOASTS } from "./NotificationToastViewport";
import { fetchNotifications, markNotificationRead } from "../services/notificationsApi";

vi.mock("../services/notificationsApi", () => ({
  fetchNotifications: vi.fn(),
  markAllNotificationsRead: vi.fn(),
  markNotificationRead: vi.fn(),
}));

vi.mock("../i18n", () => ({
  useLanguage: () => ({
    direction: "ltr",
    t: (key) => ({
      "notifications.dismissToast": "Dismiss notification",
      "notifications.fallbackTitle": "Workspace notification",
      "notifications.newToastRegion": "New notifications",
    })[key] || key,
  }),
}));

const notification = (id, path = "/notifications", kind = "notification_center") => ({
  id,
  title: `Title ${id}`,
  body: `<script>Detail ${id}</script>`,
  created_at: `2026-08-11T10:0${id}:00Z`,
  unread: true,
  data: { action: { kind, path } },
});

function CurrentPath() {
  return <output data-testid="path">{useLocation().pathname}</output>;
}

function TestApp() {
  const { refreshNotifications } = useNotifications();
  return (
    <>
      <button type="button" onClick={refreshNotifications}>Refresh notifications</button>
      <CurrentPath />
      <NotificationToastViewport />
    </>
  );
}

const renderViewport = (responses) => {
  fetchNotifications.mockResolvedValueOnce({ notifications: [], unread_count: 0 });
  for (const response of responses) fetchNotifications.mockResolvedValueOnce(response);
  return render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <NotificationProvider
        user={{ id: "user-1", tenant_id: "tenant-a" }}
        pollIntervalMs={0}
        claimToast={vi.fn().mockResolvedValue(true)}
      >
        <TestApp />
      </NotificationProvider>
    </MemoryRouter>,
  );
};

describe("NotificationToastViewport", () => {
  afterEach(cleanup);

  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    fetchNotifications.mockReset();
    markNotificationRead.mockReset();
  });

  it("renders an accessible bounded live region and drains the queue", async () => {
    renderViewport([{
      notifications: [1, 2, 3, 4].map((id) => notification(String(id))),
      unread_count: 4,
    }]);
    await waitFor(() => expect(fetchNotifications).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: "Refresh notifications" }));
    await waitFor(() => expect(document.querySelectorAll(".notification-toast")).toHaveLength(MAX_VISIBLE_TOASTS));

    const viewport = screen.getByRole("region", { name: "New notifications" });
    expect(viewport.getAttribute("aria-live")).toBe("polite");
    expect(screen.getAllByRole("button", { name: "Dismiss notification" })).toHaveLength(
      MAX_VISIBLE_TOASTS,
    );
    expect(document.body.innerHTML).not.toContain("<script>Detail");
    fireEvent.click(screen.getAllByRole("button", { name: "Dismiss notification" })[0]);
    await waitFor(() => expect(screen.getByText("Title 4")).toBeTruthy());
    expect(markNotificationRead).not.toHaveBeenCalled();
  });

  it("navigates a canonical calendar action without marking read", async () => {
    renderViewport([{
      notifications: [notification("1", "/calendar", "calendar_task")],
      unread_count: 1,
    }]);
    await waitFor(() => expect(fetchNotifications).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: "Refresh notifications" }));
    const action = await screen.findByRole("button", { name: /Title 1/ });
    expect(document.activeElement).not.toBe(action);
    fireEvent.click(action);
    expect(screen.getByTestId("path").textContent).toBe("/calendar");
    expect(markNotificationRead).not.toHaveBeenCalled();
  });

  it("falls back to the notification center for an external action", async () => {
    renderViewport([{
      notifications: [notification("1", "https://evil.example", "calendar_task")],
      unread_count: 1,
    }]);
    await waitFor(() => expect(fetchNotifications).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole("button", { name: "Refresh notifications" }));
    fireEvent.click(await screen.findByRole("button", { name: /Title 1/ }));
    expect(screen.getByTestId("path").textContent).toBe("/notifications");
  });
});
