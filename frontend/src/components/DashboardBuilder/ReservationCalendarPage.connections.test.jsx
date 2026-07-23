import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  CalendarConnectionCard,
} from "./ReservationCalendarPage";
import {
  confirmConnectedAccountDisconnect,
  confirmIncompleteConnectionRemoval,
} from "./utils/calendarConnectionPrompts";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

const pending = {
  id: "internal-connection-id",
  provider: "google",
  account_label: "Google Calendar",
  direction: "read",
  status: "setup_required",
};

const connected = {
  ...pending,
  status: "connected",
  direction: "two_way",
  last_success_at: "2026-07-23T10:00:00+00:00",
};

describe("calendar connection management", () => {
  it("shows Remove for incomplete connections without rendering an internal identifier", () => {
    const onAuthorize = vi.fn();
    const onRemove = vi.fn();
    render(
      <CalendarConnectionCard
        connection={pending}
        onAuthorize={onAuthorize}
        onSync={vi.fn()}
        onRemove={onRemove}
        onDisconnect={vi.fn()}
      />
    );

    expect(screen.getByRole("button", { name: "Authorize" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Remove" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Disconnect" })).toBeNull();
    expect(screen.queryByText(pending.id)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(onRemove).toHaveBeenCalledWith(pending);
  });

  it("shows Disconnect only for connected accounts and keeps cards distinguishable", () => {
    const onDisconnect = vi.fn();
    render(
      <CalendarConnectionCard
        connection={connected}
        onAuthorize={vi.fn()}
        onSync={vi.fn()}
        onRemove={vi.fn()}
        onDisconnect={onDisconnect}
      />
    );

    expect(screen.getByText("Google Calendar")).toBeTruthy();
    expect(screen.getByText("google · Two-way")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sync" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Disconnect" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Remove" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(onDisconnect).toHaveBeenCalledWith(connected);
  });

  it("disables repeat actions and displays progress while a request is active", () => {
    render(
      <CalendarConnectionCard
        connection={pending}
        operation="remove"
        onAuthorize={vi.fn()}
        onSync={vi.fn()}
        onRemove={vi.fn()}
        onDisconnect={vi.fn()}
      />
    );
    expect(screen.getByText("Removing…")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Authorize" }).disabled).toBe(true);
    expect(screen.getByRole("button", { name: "Remove" }).disabled).toBe(true);
  });

  it("requires explicit confirmation for removal and disconnect", () => {
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    expect(confirmIncompleteConnectionRemoval()).toBe(false);
    expect(confirmConnectedAccountDisconnect()).toBe(true);
    expect(confirm.mock.calls[1][0]).toContain("existing calendar events will remain");
  });
});
