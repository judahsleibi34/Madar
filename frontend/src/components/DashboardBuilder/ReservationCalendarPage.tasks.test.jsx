import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ReservationCalendarPage from "./ReservationCalendarPage";
import {
  createCalendarTask,
  fetchCalendarWorkspace,
} from "../PageBuilder/services/PageBuilder.api";

vi.mock("../PageBuilder/services/PageBuilder.api", () => ({
  authorizeCalendarConnection: vi.fn(),
  createCalendarConnection: vi.fn(),
  createCalendarEvent: vi.fn(),
  createCalendarTask: vi.fn(),
  deleteCalendarEvent: vi.fn(),
  disconnectCalendarConnection: vi.fn(),
  fetchCalendarEventHistory: vi.fn().mockResolvedValue([]),
  fetchCalendarWorkspace: vi.fn(),
  getCalendarExportUrl: vi.fn(() => "#"),
  importCalendarIcs: vi.fn(),
  removeCalendarConnection: vi.fn(),
  resolveCalendarInvitation: vi.fn(),
  syncCalendarConnection: vi.fn(),
  updateCalendarEvent: vi.fn(),
  updateCalendarTask: vi.fn(),
}));

vi.mock("./utils/calendarWorkspaceCache", () => ({
  clearCalendarWorkspaceCache: vi.fn(),
  createCalendarWorkspaceCacheKey: vi.fn(({ start, end }) => `${start}:${end}`),
  getOrCreateCalendarWorkspaceRequest: vi.fn((_key, loader) => loader()),
  readCalendarWorkspaceCache: vi.fn(() => null),
  writeCalendarWorkspaceCache: vi.fn(),
}));

function localIsoAt(hour, minute = 0) {
  const value = new Date();
  value.setHours(hour, minute, 0, 0);
  return value.toISOString();
}

const workspace = {
  calendar_features_available: true,
  calendars: [{
    id: "calendar-fixture",
    name: "Planning",
    color: "#336699",
    is_default: true,
  }],
  events: [],
  tasks: [
    {
      id: "scheduled-task",
      calendar_id: "calendar-fixture",
      title: "Scheduled fixture task",
      status: "todo",
      priority: "normal",
      scheduled_start: localIsoAt(10),
      scheduled_end: localIsoAt(11),
      version: 1,
    },
    {
      id: "unscheduled-task",
      calendar_id: "calendar-fixture",
      title: "Unscheduled fixture task",
      status: "in_progress",
      priority: "high",
      scheduled_start: null,
      due_at: null,
      version: 1,
    },
    {
      id: "completed-task",
      calendar_id: "calendar-fixture",
      title: "Completed fixture task",
      status: "done",
      priority: "normal",
      scheduled_start: localIsoAt(12),
      version: 1,
    },
  ],
  connections: [],
  invitation_reviews: [],
  workload: [],
  viewer_timezone: "UTC",
};

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

beforeEach(() => {
  fetchCalendarWorkspace.mockResolvedValue(workspace);
  createCalendarTask.mockResolvedValue({});
});

describe("calendar task UI", () => {
  it("renders scheduled tasks in week, day, month, and agenda while keeping unscheduled work separate", async () => {
    render(<ReservationCalendarPage user={{ id: "operator-fixture" }} />);

    expect(await screen.findByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();
    const openTasksSummary = screen.getByText("Open tasks").closest("article");
    expect(within(openTasksSummary).getByText("2")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "day" }));
    expect(screen.getByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "month" }));
    expect(screen.getByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "agenda" }));
    expect(screen.getByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Unscheduled fixture task/ })).toBeTruthy();
    expect(screen.queryByText("Completed fixture task")).toBeNull();
  });

  it("sends an explicit schedule or explicit nulls from quick add and counts both as open", async () => {
    render(<ReservationCalendarPage user={{ id: "operator-fixture" }} />);
    await screen.findByText("Open tasks");

    fireEvent.click(screen.getByRole("button", { name: /TasksScheduled and unscheduled work/ }));
    expect(screen.getByText("Unscheduled", { selector: "small" })).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Task title"), {
      target: { value: "New scheduled task" },
    });
    fireEvent.change(screen.getByLabelText("Task schedule"), {
      target: { value: "2026-07-23T14:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add task" }));

    await waitFor(() => expect(createCalendarTask).toHaveBeenCalledTimes(1));
    const scheduledPayload = createCalendarTask.mock.calls[0][0];
    expect(scheduledPayload.calendar_id).toBe("calendar-fixture");
    expect(scheduledPayload.scheduled_start).toMatch(/^2026-07-23T/);
    expect(scheduledPayload.scheduled_end).not.toBeNull();

    fireEvent.change(screen.getByLabelText("Task title"), {
      target: { value: "New unscheduled task" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add task" }));

    await waitFor(() => expect(createCalendarTask).toHaveBeenCalledTimes(2));
    expect(createCalendarTask.mock.calls[1][0]).toMatchObject({
      calendar_id: "calendar-fixture",
      due_at: null,
      scheduled_start: null,
      scheduled_end: null,
      reminder_minutes_before: null,
    });
  });
});
