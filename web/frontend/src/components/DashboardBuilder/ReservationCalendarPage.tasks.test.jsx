import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ReservationCalendarPage from "./ReservationCalendarPage";
import {
  archiveCalendarTask,
  createCalendarTask,
  createCalendarEvent,
  deleteCalendarTask,
  fetchCalendarWorkspace,
  listBuilderReservations,
  syncCalendarTask,
  updateCalendarTask,
} from "../PageBuilder/services/PageBuilder.api";
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
  listBuilderReservations: vi.fn(),
  removeCalendarConnection: vi.fn(),
  resolveCalendarInvitation: vi.fn(),
  syncCalendarConnection: vi.fn(),
  syncCalendarTask: vi.fn(),
  unlinkCalendarTaskSync: vi.fn(),
  updateCalendarEvent: vi.fn(),
  updateCalendarTask: vi.fn(),
  upgradeCalendarConnection: vi.fn(),
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
  listBuilderReservations.mockResolvedValue({ reservations: [], pagination: { has_more: false } });
  createCalendarTask.mockResolvedValue({});
  deleteCalendarTask.mockResolvedValue({});
  syncCalendarTask.mockResolvedValue({});
  archiveCalendarTask.mockResolvedValue({});
  updateCalendarTask.mockResolvedValue({});
});

describe("calendar task UI", () => {
  it("renders standalone Agenda without calendar tools and allows drafting while services are disabled", async () => {
    fetchCalendarWorkspace.mockResolvedValueOnce({ ...workspace, calendar_features_available: false });
    render(<ReservationCalendarPage user={operator} standaloneAgenda />);

    expect(await screen.findByRole("heading", { name: "My tasks", exact: true })).toBeTruthy();
    const title = await screen.findByLabelText("Task title");
    await screen.findByText(/Saving is unavailable/);
    expect(title.disabled).toBe(false);
    expect(screen.getByLabelText("Task schedule").closest("details")).toBeNull();
    fireEvent.change(title, { target: { value: "Draft my task" } });
    expect(title.value).toBe("Draft my task");
    expect(screen.getByRole("button", { name: "Add task" }).disabled).toBe(true);
    expect(screen.queryByRole("heading", { name: "Calendar", exact: true })).toBeNull();
    expect(screen.queryByRole("button", { name: "New event" })).toBeNull();
    expect(document.getElementById("calendar-workspace-tools")).toBeNull();
    expect(document.querySelector(".reservation-calendar-view-switch")).toBeNull();
    expect(screen.queryByTitle("Allow system notifications for calendar reminders")).toBeNull();
    expect(screen.queryByRole("button", { name: "Today", exact: true })).toBeNull();
    expect(screen.queryByRole("button", { name: /Refresh/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "Reset" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Task history" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Open Archive" })).toBeNull();
    fireEvent.submit(title.closest("form"));
    expect(createCalendarTask).not.toHaveBeenCalled();
  });

  it("applies date filters inclusively and rejects invalid ranges before restoring upcoming dates", async () => {
    render(<ReservationCalendarPage user={operator} standaloneAgenda />);
    await screen.findByRole("heading", { name: "My tasks", exact: true });
    await waitFor(() => expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(1));
    const initialRange = fetchCalendarWorkspace.mock.calls[0][0];
    fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "custom" } });
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-11-03" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-11-05" } });
    expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    await waitFor(() => expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(2));
    expect(fetchCalendarWorkspace.mock.calls[1][0]).toMatchObject({
      start: new Date("2026-11-03T00:00:00").toISOString(),
      end: new Date("2026-11-06T00:00:00").toISOString(),
    });
    expect(screen.getByText("Unscheduled tasks")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-11-07" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    expect(screen.getByRole("alert").textContent).toMatch(/end date on or after/);
    expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(2);
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-01-01" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2028-01-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    expect(screen.getByRole("alert").textContent).toMatch(/370 days/);
    expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(2);
    fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "month" } });
    fireEvent.change(screen.getByLabelText("Task status"), { target: { value: "open" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    await waitFor(() => expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(3));
    expect(fetchCalendarWorkspace.mock.calls[2][0]).toMatchObject({ start: initialRange.start, end: initialRange.end });
    expect(screen.getByLabelText("Date range").value).toBe("month");
    expect(screen.queryByLabelText("From")).toBeNull();
  });

  it("shows past completed tasks through the date and status filters", async () => {
    const pastStart = new Date(); pastStart.setDate(pastStart.getDate() - 10); pastStart.setHours(10, 0, 0, 0);
    const pastEnd = new Date(pastStart); pastEnd.setHours(11);
    fetchCalendarWorkspace.mockResolvedValue({ ...workspace, tasks: [...workspace.tasks, {
      id: "past-completed", calendar_id: "calendar-fixture", title: "Past completed task", status: "done",
      scheduled_start: pastStart.toISOString(), scheduled_end: pastEnd.toISOString(), version: 1,
    }, {
      id: "archived-task", calendar_id: "calendar-fixture", title: "Archived fixture task", status: "done",
      scheduled_start: pastStart.toISOString(), archived_at: pastEnd.toISOString(),
    }] });
    render(<ReservationCalendarPage user={operator} standaloneAgenda />);
    await screen.findByRole("heading", { name: "My tasks", exact: true });
    expect(screen.queryByText("Past completed task")).toBeNull();
    fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "last-month" } });
    fireEvent.change(screen.getByLabelText("Task status"), { target: { value: "all" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    expect(await screen.findByText("Past completed task")).toBeTruthy();
    expect(screen.getByLabelText("Date range").value).toBe("last-month");
    expect(screen.getByLabelText("Task status").value).toBe("all");
    expect(screen.queryByText("Archived fixture task")).toBeNull();
    expect(screen.queryByRole("link", { name: "Open Archive" })).toBeNull();
    fireEvent.change(screen.getByLabelText("Task status"), { target: { value: "done" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    expect(screen.getByText("Past completed task")).toBeTruthy();
    expect(screen.queryByText("Unscheduled fixture task")).toBeNull();
    fireEvent.change(screen.getByLabelText("Date range"), { target: { value: "month" } });
    fireEvent.change(screen.getByLabelText("Task status"), { target: { value: "open" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply filters" }));
    expect(screen.getByLabelText("Task status").value).toBe("open");
    expect(screen.queryByText("Past completed task")).toBeNull();
    expect(createCalendarTask).not.toHaveBeenCalled();
    expect(deleteCalendarTask).not.toHaveBeenCalled();
  });

  it("opens Reservations under My calendars and returns to the selected calendar view", async () => {
    render(<ReservationCalendarPage user={operator} />);
    await screen.findByText("Open tasks");

    const reservations = screen.getByRole("button", { name: "Reservations" });
    expect(reservations.closest(".calendar-calendars-panel")).toBeTruthy();
    expect(document.querySelector(".reservation-calendar-toolbar-actions")).toBeNull();
    expect(screen.getByRole("button", { name: "New event" }).closest(".calendar-calendars-panel")).toBeTruthy();
    fireEvent.click(reservations);

    expect(await screen.findByRole("heading", { name: "Reservations" })).toBeTruthy();
    expect(screen.getByLabelText("Search reservations")).toBeTruthy();
    expect(listBuilderReservations).toHaveBeenCalledWith({ limit: 100, offset: 0 });
    const views = screen.getByRole("group", { name: "Calendar view" });
    expect(within(views).getAllByRole("button").map((button) => button.textContent)).toEqual(["day", "week", "month"]);
    expect(views.contains(screen.queryByRole("button", { name: "Reservations" }))).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Back to calendar" }));
    expect(screen.getByRole("button", { name: "week" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("opens an event draft from My calendars when Calendar services are disabled", async () => {
    fetchCalendarWorkspace.mockResolvedValue({ ...workspace, calendar_features_available: false });
    render(<ReservationCalendarPage user={operator} />);
    const button = await screen.findByRole("button", { name: "New event" });
    expect(button.disabled).toBe(false);
    expect(button.closest(".calendar-calendars-panel")).toBeTruthy();
    fireEvent.click(button);
    expect(screen.getByRole("heading", { name: "Add to calendar" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Event draft" } });
    expect(screen.getByLabelText("Title").value).toBe("Event draft");
    expect(screen.getByText(/Saving is unavailable while Calendar services are disabled/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save event" }).disabled).toBe(true);
    fireEvent.submit(screen.getByRole("button", { name: "Save event" }).closest("form"));
    expect(createCalendarEvent).not.toHaveBeenCalled();
  });

  it("allows drafting without inventing a calendar and prevents saving", async () => {
    fetchCalendarWorkspace.mockResolvedValue({ ...workspace, calendars: [] });
    render(<ReservationCalendarPage user={operator} />);
    fireEvent.click(await screen.findByRole("button", { name: "New event" }));
    expect(screen.getByText("Your Madar calendar is not ready yet. You can draft an event here, but saving is unavailable.")).toBeTruthy();
    expect(screen.getByText("My Madar calendar")).toBeTruthy();
    expect(screen.queryByText("No calendars available")).toBeNull();
    expect(screen.queryByRole("combobox", { name: "Calendar" })).toBeNull();
    expect(screen.getByRole("button", { name: "Save event" }).disabled).toBe(true);
    fireEvent.submit(screen.getByRole("button", { name: "Save event" }).closest("form"));
    expect(createCalendarEvent).not.toHaveBeenCalled();
  });

  it("saves a new event through the existing API when Calendar services are available", async () => {
    createCalendarEvent.mockResolvedValue({});
    render(<ReservationCalendarPage user={operator} />);
    fireEvent.click(await screen.findByRole("button", { name: "New event" }));
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Team session" } });
    expect(screen.getByRole("button", { name: "Save event" }).disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Save event" }));
    await waitFor(() => expect(createCalendarEvent).toHaveBeenCalledWith(expect.objectContaining({ title: "Team session", calendar_id: "calendar-fixture" })));
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Add to calendar" })).toBeNull());
  });

  it("shows scheduled and undated My tasks in Calendar with a visibility toggle", async () => {
    render(<ReservationCalendarPage user={operator} />);
    await screen.findByText("Open tasks");
    const taskToggle = screen.getByRole("checkbox", { name: /My tasks/ });
    expect(taskToggle.checked).toBe(true);
    expect(screen.getByRole("heading", { name: "Tasks to schedule" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Unscheduled fixture task" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();
    fireEvent.click(taskToggle);
    expect(screen.queryByRole("heading", { name: "Tasks to schedule" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Scheduled fixture task/ })).toBeNull();
    fireEvent.click(taskToggle);
    fireEvent.click(screen.getByRole("button", { name: "Unscheduled fixture task" }));
    expect(screen.getByLabelText("Title").value).toBe("Unscheduled fixture task");
    expect(screen.getByLabelText("Start date")).toBeTruthy();
  });

  it("keeps advanced event options collapsed while allowing edits and Escape", async () => {
    render(<ReservationCalendarPage user={operator} />);
    fireEvent.click(await screen.findByRole("button", { name: "New event" }));
    const dialog = screen.getByRole("dialog", { name: "Add to calendar" });
    expect(within(dialog).getByLabelText("Title")).toBeTruthy();
    expect(within(dialog).getByLabelText("Start date")).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "Save event" })).toBeTruthy();
    const options = within(dialog).getByText("More options").closest("details");
    expect(options.open).toBe(false);
    fireEvent.click(within(dialog).getByText("More options"));
    expect(options.open).toBe(true);
    fireEvent.change(within(dialog).getByLabelText("Location"), { target: { value: "Studio" } });
    expect(within(dialog).getByLabelText("Location").value).toBe("Studio");
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Add to calendar" })).toBeNull();
  });

  it("lets users choose event times and a time zone with clear sharing and busy settings", async () => {
    createCalendarEvent.mockResolvedValue({});
    render(<ReservationCalendarPage user={operator} />);
    fireEvent.click(await screen.findByRole("button", { name: "New event" }));
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Zoned session" } });
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-01-15" } });
    fireEvent.change(screen.getByLabelText("Start time"), { target: { value: "09:30" } });
    fireEvent.change(screen.getByLabelText("End date"), { target: { value: "2026-01-15" } });
    fireEvent.change(screen.getByLabelText("End time"), { target: { value: "10:30" } });
    fireEvent.change(screen.getByLabelText(/^Time zone/), { target: { value: "America/New_York" } });
    fireEvent.click(screen.getByText("More options"));
    expect(screen.getByLabelText(/Who can see this event/).value).toBe("calendar_default");
    expect(screen.getByLabelText(/Does this block your time/).value).toBe("busy");
    fireEvent.click(screen.getByRole("button", { name: "Save event" }));
    await waitFor(() => expect(createCalendarEvent).toHaveBeenCalledWith(expect.objectContaining({ starts_at: "2026-01-15T14:30:00.000Z", ends_at: "2026-01-15T15:30:00.000Z", timezone: "America/New_York", visibility: "calendar_default", transparency: "busy" })));
  });

  it("defaults to the built-in Madar calendar when other calendars exist", async () => {
    fetchCalendarWorkspace.mockResolvedValue({ ...workspace, calendars: [
      { id: "another-calendar", name: "Team calendar" },
      { id: "calendar-fixture", name: "Personal", is_default: true },
    ] });
    render(<ReservationCalendarPage user={operator} />);
    fireEvent.click(await screen.findByRole("button", { name: "New event" }));
    expect(screen.getByLabelText("Calendar").value).toBe("calendar-fixture");
    expect(screen.getByRole("option", { name: "My Madar calendar (Personal)" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Calendar"), { target: { value: "another-calendar" } });
    expect(screen.getByLabelText("Calendar").value).toBe("another-calendar");
  });

  it("renders a fresh cache without a redundant network request", async () => {
    readCalendarWorkspaceCacheEntry.mockReturnValueOnce({
      freshness: "fresh",
      workspace: {
        ...workspace,
        tasks: [{ ...workspace.tasks[0], title: "Fresh cached task" }],
      },
    });

    render(<ReservationCalendarPage user={operator} />);

    expect(await screen.findByRole("button", { name: /Fresh cached task/ })).toBeTruthy();
    expect(fetchCalendarWorkspace).not.toHaveBeenCalled();
  });

  it("refreshes a fresh cache on focus without overlapping duplicate triggers", async () => {
    readCalendarWorkspaceCacheEntry.mockReturnValueOnce({
      freshness: "fresh",
      workspace,
    });

    render(<ReservationCalendarPage user={operator} />);
    await screen.findByText("Open tasks");
    expect(fetchCalendarWorkspace).not.toHaveBeenCalled();

    fireEvent.focus(window);
    document.dispatchEvent(new Event("visibilitychange"));

    await waitFor(() => expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(1));
  });

  it("keeps only day, week and month views on phones", async () => {
    vi.stubGlobal("matchMedia", vi.fn(() => ({
      matches: true,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    })));

    render(<ReservationCalendarPage user={operator} />);
    await screen.findByText("Open tasks");

    expect(screen.getByRole("button", { name: "day" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "week" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "agenda" })).toBeNull();
    expect(screen.getByRole("button", { name: "month" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Reservations" })).toBeTruthy();
    expect(document.querySelector(".calendar-month-grid")).toBeTruthy();
    expect(document.querySelector(".calendar-month-weekdays").textContent)
      .toBe("SunMonTueWedThuFriSat");
    expect(screen.getByText(new Date().toLocaleDateString(undefined, { month: "long", year: "numeric" })))
      .toBeTruthy();
    const toolsToggle = screen.getByRole("button", { name: "Calendar tools" });
    expect(toolsToggle.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(toolsToggle);
    expect(toolsToggle.getAttribute("aria-expanded")).toBe("true");
    expect(document.getElementById("calendar-workspace-tools").classList.contains("is-mobile-open"))
      .toBe(true);
  });

  it("does not prefetch a removed Agenda tab", async () => {
    render(<ReservationCalendarPage user={operator} />);
    await screen.findByText("Open tasks");
    await waitFor(() => expect(writeCalendarWorkspaceCache).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("button", { name: "agenda" })).toBeNull();
    fireEvent.pointerEnter(screen.getByRole("button", { name: "day" }));
    expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(1);
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
    expect(screen.getByLabelText("Start date").value).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(screen.getByLabelText("Start time").value).toBe("00:00");

    const endTimeToggle = screen.getByLabelText("Add an end date and time");
    expect(endTimeToggle.checked).toBe(false);
    expect(screen.queryByLabelText("End date")).toBeNull();

    fireEvent.click(endTimeToggle);
    expect(screen.getByLabelText("End date")).toBeTruthy();
    expect(screen.getByLabelText("End time")).toBeTruthy();

    fireEvent.click(endTimeToggle);
    expect(screen.queryByLabelText("End date")).toBeNull();
  });

  it("renders scheduled tasks in week, day, month, and agenda while keeping unscheduled work separate", async () => {
    const page = render(<ReservationCalendarPage user={operator} />);

    expect(await screen.findByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();
    const openTasksSummary = screen.getByText("Open tasks").closest("article");
    expect(within(openTasksSummary).getByText("2")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "day" }));
    expect(screen.getByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "month" }));
    expect(screen.getByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();

    page.unmount();
    render(<ReservationCalendarPage user={operator} standaloneAgenda />);
    await screen.findByLabelText("Task title");
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
    expect(screen.getByLabelText("Add an end date and time").checked).toBe(false);
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Task from date" } });
    fireEvent.click(screen.getByRole("button", { name: "Save task" }));

    await waitFor(() => expect(createCalendarTask).toHaveBeenCalledTimes(1));
    expect(createCalendarTask.mock.calls[0][0]).toMatchObject({
      calendar_id: "calendar-fixture",
      title: "Task from date",
    });
    expect(createCalendarTask.mock.calls[0][0].scheduled_start).toBeTruthy();
    expect(createCalendarTask.mock.calls[0][0].scheduled_end).toBeNull();
  });

  it("sends an explicit schedule or explicit nulls from quick add and counts both as open", async () => {
    render(<ReservationCalendarPage user={operator} initialView="agenda" />);
    await screen.findByText("Open tasks");

    expect(within(document.getElementById("calendar-workspace-tools")).queryByLabelText("Task title"))
      .toBeNull();
    expect(screen.getByText("Unscheduled tasks")).toBeTruthy();

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
    expect(scheduledPayload.scheduled_end).toBeNull();

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
    render(<ReservationCalendarPage user={operator} initialView="agenda" />);
    await screen.findByText("Open tasks");

    fireEvent.click(screen.getByRole("button", { name: "Archive Scheduled fixture task" }));
    expect(screen.getByRole("dialog", { name: "Archive this task?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Archive task" }));

    expect(archiveCalendarTask).toHaveBeenCalledWith("scheduled-task", 1);
    await waitFor(() => expect(fetchCalendarWorkspace).toHaveBeenCalledTimes(2));
  });

  it("deletes an Agenda task directly beside its archive action", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<ReservationCalendarPage user={operator} initialView="agenda" />);
    await screen.findByText("Open tasks");

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

    const { container } = render(<ReservationCalendarPage user={operator} initialView="agenda" />);
    await screen.findByText("Open tasks");
    expect(container.querySelector(".reservation-calendar-loading")).toBeNull();

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

  it("keeps advanced fields out of the editor and confirms task deletion", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<ReservationCalendarPage user={operator} initialView="agenda" />);

    fireEvent.click((await screen.findAllByRole("button", { name: /Scheduled fixture task/ }))
      .find((button) => button.classList.contains("calendar-agenda-task")));
    expect(screen.getByRole("button", { name: "Delete" })).toBeTruthy();
    expect(screen.queryByText("More options")).toBeNull();
    expect(screen.queryByLabelText("Time needed (minutes)")).toBeNull();
    expect(screen.queryByLabelText("Add to calendar")).toBeNull();
    expect(screen.queryByLabelText("Finish by")).toBeNull();
    expect(screen.queryByLabelText(/Notes/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    fireEvent.click(screen.getAllByRole("button", { name: /Unscheduled fixture task/ })
      .find((button) => button.classList.contains("calendar-agenda-task")));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete task" }));
    await waitFor(() =>
      expect(deleteCalendarTask).toHaveBeenCalledWith(
        "unscheduled-task",
        "local_only"
      )
    );
  });

  it("preserves existing provider sync while reporting enqueue failure separately", async () => {
    fetchCalendarWorkspace.mockResolvedValue({
      ...workspace,
      tasks: workspace.tasks.map((task) => task.id === "scheduled-task"
        ? {
            ...task,
            sync_connection_id: "private-connection-id",
            is_synchronized: false,
          }
        : task),
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
    expect(screen.queryByText("private-connection-id")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Save task" }));

    expect(await screen.findByText(/Task saved, but Google synchronization could not be queued/)).toBeTruthy();
    expect(syncCalendarTask).toHaveBeenCalledWith("scheduled-task", "private-connection-id");
    expect(screen.queryByRole("button", { name: "Save task" })).toBeNull();
    expect(screen.getByRole("button", { name: /Scheduled fixture task/ })).toBeTruthy();
  });
});
