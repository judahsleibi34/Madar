import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ReservationCalendarPage from "./ReservationCalendarPage";
import {
  archiveCalendarTask,
  createCalendarTask,
  deleteCalendarTask,
  fetchCalendarWorkspace,
  syncCalendarTask,
  updateCalendarTask,
} from "../PageBuilder/services/PageBuilder.api";
import { archiveItem } from "../PageBuilder/DataAnalysisWorkspace/utils/datasetStorage";
import {
  readCalendarWorkspaceCacheEntry,
  writeCalendarWorkspaceCache,
} from "./utils/calendarWorkspaceCache";

vi.mock("../PageBuilder/services/PageBuilder.api", () => ({
  archiveCalendarTask: vi.fn(),
  authorizeCalendarConnection: vi.fn(),
  createCalendarConnection: vi.fn(),
  createCalendarEvent: vi.fn(),
  createCalendarTask: vi.fn(),
  deleteCalendarTask: vi.fn(),
  deleteCalendarEvent: vi.fn(),
  disconnectCalendarConnection: vi.fn(),
  fetchCalendarEventHistory: vi.fn().mockResolvedValue([]),
  fetchCalendarWorkspace: vi.fn(),
  getCalendarExportUrl: vi.fn(() => "#"),
  importCalendarIcs: vi.fn(),
  removeCalendarConnection: vi.fn(),
  resolveCalendarInvitation: vi.fn(),
  syncCalendarConnection: vi.fn(),
  syncCalendarTask: vi.fn(),
  unlinkCalendarTaskSync: vi.fn(),
  updateCalendarEvent: vi.fn(),
  updateCalendarTask: vi.fn(),
  upgradeCalendarConnection: vi.fn(),
}));

vi.mock("../PageBuilder/DataAnalysisWorkspace/utils/datasetStorage", () => ({
  archiveItem: vi.fn(),
  deleteArchiveItem: vi.fn(),
}));

vi.mock("./utils/calendarWorkspaceCache", () => ({
  clearCalendarWorkspaceCache: vi.fn(),
  createCalendarWorkspaceCacheKey: vi.fn(
    ({ tenantScope, userScope, start, end }) => `${tenantScope}:${userScope}:${start}:${end}`
  ),
  getOrCreateCalendarWorkspaceRequest: vi.fn((_key, loader) => loader()),
  readCalendarWorkspaceCacheEntry: vi.fn(() => null),
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

const operator = { id: "operator-fixture", tenant_id: "tenant-a" };

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

beforeEach(() => {
  fetchCalendarWorkspace.mockResolvedValue(workspace);
  createCalendarTask.mockResolvedValue({});
  deleteCalendarTask.mockResolvedValue({});
  syncCalendarTask.mockResolvedValue({});
  archiveCalendarTask.mockResolvedValue({});
  archiveItem.mockResolvedValue("calendar-task-scheduled-task");
  updateCalendarTask.mockResolvedValue({});
});

describe("calendar task UI", () => {
  it("offers both Calendar and Agenda views on phones", async () => {
    vi.stubGlobal("matchMedia", vi.fn(() => ({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    })));

    render(<ReservationCalendarPage user={operator} />);
    await screen.findByText("Open tasks");

    expect(screen.getByRole("button", { name: "calendar" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "agenda" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "week" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "calendar" }));
    expect(document.querySelector(".calendar-month-grid")).toBeTruthy();
  });

  it("prewarms and stores the Agenda range before switching views", async () => {
    render(<ReservationCalendarPage user={operator} />);
    await screen.findByText("Open tasks");
    await waitFor(() => expect(writeCalendarWorkspaceCache).toHaveBeenCalledTimes(1));

    fireEvent.pointerEnter(screen.getByRole("button", { name: "agenda" }));

    await waitFor(() => expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(2));
    const agendaRequest = fetchCalendarWorkspace.mock.calls[1][0];
    expect(
      (new Date(agendaRequest.end) - new Date(agendaRequest.start)) / 86_400_000
    ).toBe(31);
    await waitFor(() => expect(writeCalendarWorkspaceCache).toHaveBeenCalledTimes(2));
  });

  it("paints stale cached workspace immediately and refreshes it in the background", async () => {
    let resolveNetwork;
    const network = new Promise((resolve) => {
      resolveNetwork = resolve;
    });
    readCalendarWorkspaceCacheEntry.mockReturnValueOnce({
      freshness: "stale",
      workspace: {
        ...workspace,
        tasks: [{ ...workspace.tasks[0], title: "Cached scheduled task" }],
      },
    });
    fetchCalendarWorkspace.mockReturnValueOnce(network);

    render(<ReservationCalendarPage user={operator} />);

    expect(await screen.findByRole("button", { name: /Cached scheduled task/ })).toBeTruthy();
    expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(1);
    expect(writeCalendarWorkspaceCache).not.toHaveBeenCalled();

    resolveNetwork(workspace);
    expect(await screen.findByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();
    expect(writeCalendarWorkspaceCache).toHaveBeenCalledTimes(1);
  });

  it("opens the chooser from an empty week rectangle and keeps its exact hour", async () => {
    render(<ReservationCalendarPage user={operator} />);
    await screen.findByText("Open tasks");

    const midnightSlot = screen.getAllByRole("button", { name: /Add to .*12 AM/i })[0];
    fireEvent.click(midnightSlot);
    expect(screen.getByRole("dialog", { name: "What would you like to add?" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Create task/ }));
    expect(screen.getByLabelText("Scheduled start").value).toMatch(/T00:00$/);
  });

  it("renders scheduled tasks in week, day, month, and agenda while keeping unscheduled work separate", async () => {
    render(<ReservationCalendarPage user={operator} />);

    expect(await screen.findByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();
    const openTasksSummary = screen.getByText("Open tasks").closest("article");
    expect(within(openTasksSummary).getByText("2")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "day" }));
    expect(screen.getByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "month" }));
    expect(screen.getByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "agenda" }));
    expect(screen.getAllByRole("button", { name: /Scheduled fixture task/ }).some(
      (button) => button.classList.contains("calendar-agenda-task")
    )).toBe(true);
    expect(screen.getAllByRole("button", { name: /Unscheduled fixture task/ }).some(
      (button) => button.classList.contains("calendar-agenda-task")
    )).toBe(true);
    expect(screen.queryByText("Completed fixture task")).toBeNull();
  });

  it("opens a date chooser and creates a task or reservation on the selected day", async () => {
    render(<ReservationCalendarPage user={operator} />);
    await screen.findByText("Open tasks");

    fireEvent.click(screen.getByRole("button", { name: "month" }));
    const dateButton = screen.getAllByRole("button", { name: /^Add to / })[10];
    fireEvent.click(dateButton);

    expect(screen.getByRole("dialog", { name: "What would you like to add?" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Create task/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Reserve time/ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Reserve time/ }));
    expect(screen.getByRole("heading", { name: "Add to calendar" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));

    fireEvent.click(dateButton);
    fireEvent.click(screen.getByRole("button", { name: /Create task/ }));
    expect(screen.getByRole("heading", { name: "Add a task" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Task from date" } });
    fireEvent.click(screen.getByRole("button", { name: "Save task" }));

    await waitFor(() => expect(createCalendarTask).toHaveBeenCalledTimes(1));
    expect(createCalendarTask.mock.calls[0][0]).toMatchObject({
      calendar_id: "calendar-fixture",
      title: "Task from date",
    });
    expect(createCalendarTask.mock.calls[0][0].scheduled_start).toBeTruthy();
  });

  it("sends an explicit schedule or explicit nulls from quick add and counts both as open", async () => {
    render(<ReservationCalendarPage user={operator} />);
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

  it("archives an Agenda task and removes it from the active Calendar workspace", async () => {
    render(<ReservationCalendarPage user={operator} />);
    await screen.findByText("Open tasks");

    fireEvent.click(screen.getByRole("button", { name: "agenda" }));
    fireEvent.click(screen.getByRole("button", { name: "Archive Scheduled fixture task" }));
    expect(screen.getByRole("dialog", { name: "Archive this task?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Archive task" }));

    await waitFor(() => expect(archiveItem).toHaveBeenCalledWith(expect.objectContaining({
      id: "calendar-task-scheduled-task",
      type: "task",
      scope: "user-operator-fixture",
      title: "Scheduled fixture task",
    })));
    expect(archiveCalendarTask).toHaveBeenCalledWith("scheduled-task", 1);
    await waitFor(() => expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(2));
  });

  it("deletes an Agenda task directly beside its archive action", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<ReservationCalendarPage user={operator} />);
    await screen.findByText("Open tasks");

    fireEvent.click(screen.getByRole("button", { name: "agenda" }));
    const archiveButton = screen.getByRole("button", { name: "Archive Scheduled fixture task" });
    const deleteButton = screen.getByRole("button", { name: "Delete Scheduled fixture task" });

    expect(deleteButton.parentElement).toBe(archiveButton.parentElement);
    fireEvent.click(deleteButton);
    expect(screen.getByRole("dialog", { name: "Delete this task?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Delete task" }));

    await waitFor(() => expect(deleteCalendarTask).toHaveBeenCalledWith("scheduled-task", "local_only"));
    await waitFor(() => expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(2));
  });

  it("keeps the rendered calendar visible while revalidating after a mutation", async () => {
    let resolveRefresh;
    const refresh = new Promise((resolve) => {
      resolveRefresh = resolve;
    });
    fetchCalendarWorkspace
      .mockResolvedValueOnce(workspace)
      .mockReturnValueOnce(refresh);
    createCalendarTask.mockResolvedValue({
      id: "new-task",
      calendar_id: "calendar-fixture",
      title: "Quiet refresh task",
      status: "todo",
      priority: "normal",
    });

    const { container } = render(<ReservationCalendarPage user={operator} />);
    await screen.findByText("Open tasks");
    expect(container.querySelector(".reservation-calendar-loading")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /TasksScheduled and unscheduled work/ }));
    fireEvent.change(screen.getByLabelText("Task title"), {
      target: { value: "Quiet refresh task" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add task" }));

    await waitFor(() => expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(2));
    expect(container.querySelector(".reservation-calendar-loading")).toBeNull();
    expect(container.querySelector(".reservation-calendar-surface")).toBeTruthy();

    resolveRefresh(workspace);
  });

  it("closes immediately and updates the calendar while a scheduled task save is pending", async () => {
    let resolveSave;
    updateCalendarTask.mockReturnValueOnce(new Promise((resolve) => {
      resolveSave = resolve;
    }));
    render(<ReservationCalendarPage user={operator} />);

    fireEvent.click(await screen.findByRole("button", { name: /Scheduled fixture task/ }));
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Instant scheduled task" } });
    fireEvent.click(screen.getByRole("button", { name: "Save task" }));

    expect(screen.queryByRole("button", { name: "Save task" })).toBeNull();
    expect(screen.getByRole("button", { name: /Instant scheduled task/ })).toBeTruthy();
    expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(1);

    resolveSave({
      ...workspace.tasks[0],
      title: "Instant scheduled task",
      version: 2,
    });
    await waitFor(() => expect(updateCalendarTask).toHaveBeenCalledTimes(1));
  });

  it("offers explicit Google sync and confirmed task deletion without exposing identifiers", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    fetchCalendarWorkspace.mockResolvedValue({
      ...workspace,
      connections: [{
        id: "private-connection-id",
        provider: "google",
        account_label: "Operator Google Calendar",
        direction: "two_way",
        status: "connected",
      }],
    });
    render(<ReservationCalendarPage user={operator} />);

    fireEvent.click(await screen.findByRole("button", { name: /Scheduled fixture task/ }));
    expect(screen.getByRole("button", { name: "Delete" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Calendar sync"), {
      target: { value: "private-connection-id" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save task" }));
    await waitFor(() =>
      expect(syncCalendarTask).toHaveBeenCalledWith(
        "scheduled-task",
        "private-connection-id"
      )
    );

    fireEvent.click(screen.getByRole("button", { name: /TasksScheduled and unscheduled work/ }));
    fireEvent.click(await screen.findByRole("button", { name: /Unscheduled fixture task/ }));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete task" }));
    await waitFor(() =>
      expect(deleteCalendarTask).toHaveBeenCalledWith(
        "unscheduled-task",
        "local_only"
      )
    );
    expect(screen.queryByText("private-connection-id")).toBeNull();
  });

  it("reports provider enqueue failure separately from a successful local save", async () => {
    fetchCalendarWorkspace.mockResolvedValue({
      ...workspace,
      connections: [{
        id: "private-connection-id",
        provider: "google",
        account_label: "Operator Google Calendar",
        direction: "two_way",
        status: "connected",
      }],
    });
    syncCalendarTask.mockRejectedValueOnce(new Error("Queue unavailable."));
    render(<ReservationCalendarPage user={operator} />);

    fireEvent.click(await screen.findByRole("button", { name: /Scheduled fixture task/ }));
    fireEvent.change(screen.getByLabelText("Calendar sync"), {
      target: { value: "private-connection-id" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save task" }));

    expect(await screen.findByText(/Task saved, but Google synchronization could not be queued/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Save task" })).toBeNull();
    expect(screen.getByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();
  });
});
