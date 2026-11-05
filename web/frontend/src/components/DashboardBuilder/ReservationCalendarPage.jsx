import DateTimeInput from "../common/DateTimeInput";
import AgendaDateTimePicker from "./AgendaDateTimePicker";
import PageHeaderSkeleton from "../common/PageHeaderSkeleton";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  Archive,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  History,
  Link2,
  ListTodo,
  Plus,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";

import {
  archiveCalendarTask,
  createCalendarConnection,
  authorizeCalendarConnection,
  createCalendarEvent,
  createCalendarTask,
  deleteCalendarTask,
  deleteCalendarEvent,
  disconnectCalendarConnection,
  fetchCalendarEventHistory,
  fetchCalendarWorkspace,
  resolveCalendarInvitation,
  removeCalendarConnection,
  setCalendarInboundSync,
  syncCalendarTask,
  syncCalendarConnection,
  unlinkCalendarTaskSync,
  upgradeCalendarConnection,
  updateCalendarEvent,
  updateCalendarTask,
} from "../PageBuilder/services/PageBuilder.api";
import PageDeleteConfirmModal from "../PageBuilder/modals/PageDeleteConfirmModal";
import CalendarReservationsTable from "./CalendarReservationsTable";
import { eventWallTime, eventTimeToInstant, eventTimeZones } from "./utils/calendarEventTime";
import {
  clearCalendarWorkspaceCache,
  createCalendarWorkspaceCacheKey,
  getOrCreateCalendarWorkspaceRequest,
  readCalendarWorkspaceCacheEntry,
  writeCalendarWorkspaceCache,
} from "./utils/calendarWorkspaceCache";
import {
  confirmConnectedAccountDisconnect,
  confirmGoogleWriteUpgrade,
  confirmIncompleteConnectionRemoval,
} from "./utils/calendarConnectionPrompts";
import {
  expandTaskOccurrences,
  taskIsOpen,
  taskPlacementStart,
} from "./utils/calendarTaskSchedule";

const HOURS = Array.from({ length: 24 }, (_, index) => index);
const CALENDAR_VIEWS = ["day", "week", "month"];
const VIEWS = [...CALENDAR_VIEWS, "agenda", "reservations"];
const PHONE_AGENDA_QUERY = "(max-width: 680px)";
const pad = (value) => String(value).padStart(2, "0");

const phoneAgendaMatches = () =>
  typeof window !== "undefined" &&
  typeof window.matchMedia === "function" &&
  window.matchMedia(PHONE_AGENDA_QUERY).matches;

function SidebarSectionHeading({ section, icon, title, subtitle, count, expanded, onToggle }) {
  return (
    <button type="button" className="calendar-sidebar-group-heading" aria-expanded={expanded} aria-controls={`calendar-sidebar-${section}`} onClick={() => onToggle(section)}>
      <span className="calendar-sidebar-heading-main"><span className="calendar-sidebar-icon">{icon}</span><span><strong>{title}</strong><small>{subtitle}</small></span></span>
      <span className="calendar-sidebar-heading-actions"><span className="calendar-count-badge">{count}</span><ChevronDown className="calendar-sidebar-chevron" size={15} /></span>
    </button>
  );
}

export function CalendarConnectionCard({ connection, operation = "", onAuthorize, onSync, onInboundToggle, onUpgrade, onRemove, onDisconnect }) {
  const connected = connection.status === "connected" || connection.status === "degraded";
  const pending = connection.status === "setup_required";
  const busy = Boolean(operation);
  const progressLabels = {
    authorize: "Authorizing…",
    upgrade: "Opening consent…",
    disconnect: "Disconnecting…",
    remove: "Removing…",
    sync: "Syncing…",
    inbound: "Updating…",
  };
  const inboundActive = connection.inbound_sync_enabled !== false;
  const inboundBusy = ["pending", "syncing"].includes(connection.inbound_sync_status);
  const status = busy
    ? (progressLabels[operation] || "Working…")
    : !inboundActive
      ? "Inbound paused"
      : connection.inbound_sync_status === "failed"
        ? "Inbound sync failed"
        : inboundBusy
          ? connection.inbound_sync_status === "pending" ? "Inbound queued" : "Inbound syncing"
          : connection.last_inbound_success_at
            ? `Inbound synced ${new Date(connection.last_inbound_success_at).toLocaleString()}`
            : connection.status.replaceAll("_", " ");
  return (
    <div className={`calendar-sync-row is-${connection.status}`}>
      <span className="calendar-sync-provider-icon">{connected ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}</span>
      <span className="calendar-sync-account">
        <strong>{connection.account_label || connection.provider}</strong>
        <small>{connection.provider === "microsoft" ? "Outlook" : connection.provider} · {connection.direction === "two_way" ? "Two-way" : "Read only"}</small>
        {connected && <small>Importing: {connection.provider_calendar_label || "Primary provider calendar"}</small>}
      </span>
      <span className="calendar-sync-status">{status}</span>
      <span className="calendar-sync-actions">
        {pending && <button type="button" disabled={busy} onClick={() => onAuthorize(connection)}>Authorize</button>}
        {connected && inboundActive && <button type="button" disabled={busy || inboundBusy} onClick={() => onSync(connection)}>Sync</button>}
        {connected && <button type="button" disabled={busy || inboundBusy} onClick={() => onInboundToggle(connection, !inboundActive)}>{inboundActive ? "Pause import" : "Enable import"}</button>}
        {connected && connection.provider === "google" && connection.direction === "read" && <button type="button" disabled={busy} onClick={() => onUpgrade(connection)}>Enable write access</button>}
        {!connected && <button type="button" className="is-danger" disabled={busy} onClick={() => onRemove(connection)}>Remove</button>}
        {connected && <button type="button" className="is-danger" disabled={busy} onClick={() => onDisconnect(connection)}>Disconnect</button>}
      </span>
    </div>
  );
}

function addDays(date, amount) {
  const result = new Date(date);
  result.setDate(result.getDate() + amount);
  return result;
}

function startOfDay(date) {
  const result = new Date(date);
  result.setHours(0, 0, 0, 0);
  return result;
}

function startOfWeek(date) {
  const result = startOfDay(date);
  result.setDate(result.getDate() - result.getDay());
  return result;
}

function rangeForView(focusDate, view) {
  if (view === "day") return [startOfDay(focusDate), addDays(startOfDay(focusDate), 1)];
  if (view === "week") {
    const start = startOfWeek(focusDate);
    return [start, addDays(start, 7)];
  }
  if (view === "agenda") return [startOfDay(focusDate), addDays(startOfDay(focusDate), 31)];
  const first = new Date(focusDate.getFullYear(), focusDate.getMonth(), 1);
  const start = startOfWeek(first);
  return [start, addDays(start, 42)];
}

function dateKey(value) {
  const date = value instanceof Date ? value : new Date(value);
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function agendaDateRange(days = 30, past = false) {
  const today = startOfDay(new Date());
  return past
    ? { from: dateKey(addDays(today, 1 - days)), to: dateKey(today) }
    : { from: dateKey(today), to: dateKey(addDays(today, days - 1)) };
}

function sameDay(first, second) {
  return dateKey(first) === dateKey(second);
}

function localInputValue(value) {
  const date = value ? new Date(value) : new Date();
  return `${dateKey(date)}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function formatTime(value) {
  return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(new Date(value));
}

function formatRange(start, end) {
  const options = { month: "short", day: "numeric", year: "numeric" };
  return `${new Intl.DateTimeFormat(undefined, options).format(start)} – ${new Intl.DateTimeFormat(undefined, options).format(addDays(end, -1))}`;
}

function blankEditor(calendarId, focusDate, timezone, useSelectedTime = false) {
  const start = new Date(focusDate);
  if (useSelectedTime) start.setMinutes(0, 0, 0);
  else start.setHours(Math.max(9, new Date().getHours() + 1), 0, 0, 0);
  const end = new Date(start.getTime() + 60 * 60 * 1000);
  const zone = timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  return {
    id: "",
    calendar_id: calendarId,
    title: "",
    description: "",
    location: "",
    starts_at: eventWallTime(start, zone),
    ends_at: eventWallTime(end, zone),
    timezone: zone,
    visibility: "calendar_default",
    transparency: "busy",
    recurrence: "none",
    reminder: "15",
    expected_version: null,
    allow_conflicts: false,
  };
}

function eventEditorValue(event) {
  return {
    ...blankEditor(event.calendar_id, new Date(event.starts_at), event.timezone),
    ...event,
    starts_at: eventWallTime(event.starts_at, event.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"),
    ends_at: eventWallTime(event.ends_at, event.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"),
    recurrence: event.recurrence_rule?.includes("FREQ=DAILY")
      ? "daily"
      : event.recurrence_rule?.includes("FREQ=WEEKLY")
        ? "weekly"
        : event.recurrence_rule?.includes("FREQ=MONTHLY")
          ? "monthly"
          : "none",
    expected_version: event.version,
    recurrence_scope: event.occurrence_start ? "occurrence" : "series",
  };
}

function taskEditorValue(task) {
  return {
    ...task,
    description: task.description || "",
    status: task.status || "todo",
    priority: task.priority || "normal",
    estimate_minutes: task.estimate_minutes || "",
    reminder_minutes_before: task.reminder_minutes_before ?? 10,
    repeat: task.recurrence_rule?.includes("FREQ=DAILY")
      ? "daily"
      : task.recurrence_rule?.includes("FREQ=WEEKLY")
        ? "weekly"
        : task.recurrence_rule?.includes("FREQ=MONTHLY")
          ? "monthly"
          : "none",
    due_at: task.due_at ? localInputValue(task.due_at) : "",
    scheduled_start: task.scheduled_start ? localInputValue(task.scheduled_start) : "",
    scheduled_end: task.scheduled_end ? localInputValue(task.scheduled_end) : "",
    sync_connection_id: task.sync_connection_id || "",
  };
}

function blankTaskEditor(calendarId, focusDate, useSelectedTime = false) {
  const start = new Date(focusDate);
  if (useSelectedTime) start.setMinutes(0, 0, 0);
  else start.setHours(9, 0, 0, 0);
  return taskEditorValue({
    id: "",
    calendar_id: calendarId,
    title: "",
    description: "",
    status: "todo",
    priority: "normal",
    scheduled_start: start.toISOString(),
    scheduled_end: null,
    due_at: null,
    reminder_minutes_before: 10,
    recurrence_rule: null,
    milestone: false,
  });
}

function recurrenceRule(value) {
  if (value === "daily") return "FREQ=DAILY";
  if (value === "weekly") return "FREQ=WEEKLY";
  if (value === "monthly") return "FREQ=MONTHLY";
  return null;
}

function EventEditor({ value, calendars, saving, conflict, unavailableReason, onChange, onClose, onSave, onDelete }) {
  const timeZones = useMemo(() => eventTimeZones(value.timezone), [value.timezone]);
  return (
    <div className="calendar-modal-backdrop" role="presentation">
      <form className="calendar-modal calendar-event-editor" role="dialog" aria-modal="true" aria-labelledby="calendar-event-title" onSubmit={onSave} onKeyDown={(event) => {
        if (event.key === "Escape") { event.stopPropagation(); onClose(); }
        if (event.key !== "Tab") return;
        const controls = [...event.currentTarget.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary')].filter((element) => element.getClientRects().length);
        const first = controls[0]; const last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }}>
        <header>
          <div>
            <h2 id="calendar-event-title">{value.id ? value.title || "Edit event" : "Add to calendar"}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close"><X size={19} /></button>
        </header>
        <div className="calendar-event-body">
        {conflict && (
          <div className="calendar-conflict-warning">
            <AlertTriangle size={18} />
            <div><strong>Check event details</strong><span>{conflict}</span></div>
          </div>
        )}
        {unavailableReason && <p className="calendar-event-unavailable" role="status">{unavailableReason}</p>}
        <label>Title<input autoFocus required placeholder="e.g. Team meeting" value={value.title} onChange={(event) => onChange("title", event.target.value)} /></label>
        <div className="calendar-form-grid">
          <TaskDateTimeFields required label="Start" value={value.starts_at} onChange={(next) => onChange("starts_at", next)} />
          <TaskDateTimeFields required label="End" value={value.ends_at} onChange={(next) => onChange("ends_at", next)} />
          {calendars.length > 1 ? <label>Calendar<select required value={value.calendar_id} onChange={(event) => onChange("calendar_id", event.target.value)}>{calendars.map((calendar) => <option key={calendar.id} value={calendar.id}>{calendar.is_default ? `My Madar calendar (${calendar.name})` : calendar.name}</option>)}</select></label> : <div className="calendar-event-destination"><span>Calendar</span><strong>{!calendars.length || calendars[0].is_default ? "My Madar calendar" : calendars[0].name}</strong></div>}
        </div>
        <label className="calendar-event-timezone-label">Time zone<select value={value.timezone} onChange={(event) => onChange("timezone", event.target.value)}>{timeZones.map((zone) => <option key={zone} value={zone}>{zone === "UTC" ? "UTC — Coordinated Universal Time" : zone.replaceAll("_", " ").replaceAll("/", " / ")}</option>)}</select><small>Start and end times use this time zone.</small></label>
        <details className="calendar-event-options" open={value.id && value.recurrence !== "none" ? true : undefined}>
          <summary>More options</summary>
          <p className="calendar-event-options-help">Repeat, reminders, sharing, location, and notes.</p>
          <div className="calendar-form-grid">
          <label>Repeat<select value={value.recurrence} onChange={(event) => onChange("recurrence", event.target.value)}><option value="none">Does not repeat</option><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select></label>
          <label>Reminder<select value={value.reminder} onChange={(event) => onChange("reminder", event.target.value)}><option value="0">At start</option><option value="10">10 minutes before</option><option value="15">15 minutes before</option><option value="60">1 hour before</option><option value="1440">1 day before</option></select></label>
          <label>Who can see this event?<select value={value.visibility} onChange={(event) => onChange("visibility", event.target.value)}><option value="calendar_default">Use calendar sharing settings</option><option value="private">Only me</option><option value="team">My team</option><option value="organization">My organization</option><option value="public">Public</option></select><small>Controls who can view the event, subject to calendar access permissions.</small></label>
          <label>Does this block your time?<select value={value.transparency} onChange={(event) => onChange("transparency", event.target.value)}><option value="busy">Yes — mark me busy</option><option value="free">No — keep me available</option></select><small>Busy time is checked for scheduling overlaps. It does not change who can see the event.</small></label>
        </div>
        <label>Location<input value={value.location} onChange={(event) => onChange("location", event.target.value)} /></label>
        <label>Notes<textarea rows="3" value={value.description} onChange={(event) => onChange("description", event.target.value)} /></label>
        <label className="calendar-checkbox"><input type="checkbox" checked={value.allow_conflicts} onChange={(event) => onChange("allow_conflicts", event.target.checked)} /><span>Save even if this overlaps another busy event</span></label>
        {value.id && value.recurrence !== "none" && (
          <div className="calendar-recurrence-scope">
            <strong>Apply this change to</strong>
            <div>
              <label><input type="radio" name="recurrence-scope" checked={value.recurrence_scope === "occurrence"} onChange={() => onChange("recurrence_scope", "occurrence")} />This occurrence</label>
              <label><input type="radio" name="recurrence-scope" checked={value.recurrence_scope === "future"} onChange={() => onChange("recurrence_scope", "future")} />This and future</label>
              <label><input type="radio" name="recurrence-scope" checked={value.recurrence_scope === "series"} onChange={() => onChange("recurrence_scope", "series")} />Entire series</label>
            </div>
            <small>{value.recurrence_scope === "occurrence" ? "Only the selected date changes; the series remains intact." : value.recurrence_scope === "future" ? "The current series ends before this date and a new series begins here." : "Every occurrence in the series will use these changes."}</small>
          </div>
        )}
        </details>
        </div>
        <div className="calendar-modal-actions">
          {value.id && <button type="button" className="is-danger" onClick={onDelete}><Trash2 size={16} /> Delete</button>}
          <span />
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="submit" className="is-primary" disabled={saving || Boolean(unavailableReason)}>{saving ? "Saving…" : "Save event"}</button>
        </div>
      </form>
    </div>
  );
}

function TaskDateTimeFields({ label, value, onChange, required = false }) {
  const dateValue = value?.slice(0, 10) || "";
  const timeValue = value?.slice(11, 16) || "";
  const updateDate = (nextDate) => onChange(nextDate ? `${nextDate}T${timeValue || "09:00"}` : "");
  const updateTime = (nextTime) => onChange(dateValue && nextTime ? `${dateValue}T${nextTime}` : value);

  return (
    <fieldset className="calendar-task-date-time-field">
      <legend>{label}</legend>
      <div>
        <label>Date<DateTimeInput required={required} type="date" aria-label={`${label} date`} value={dateValue} onChange={(event) => updateDate(event.target.value)} /></label>
        <label>Time<DateTimeInput required={required} type="time" aria-label={`${label} time`} value={timeValue} disabled={!dateValue} onChange={(event) => updateTime(event.target.value)} /></label>
      </div>
    </fieldset>
  );
}

function TaskEditor({ value: initialValue, saving, error, notice, onClose, onSave, onArchive, onDelete }) {
  const [value, setValue] = useState(initialValue);
  const [includeEndTime, setIncludeEndTime] = useState(() => Boolean(initialValue.scheduled_end));
  const onChange = (field, nextValue) => {
    setValue((current) => ({ ...current, [field]: nextValue }));
  };
  return (
    <div className="calendar-modal-backdrop" role="presentation">
      <form
        className="calendar-modal calendar-task-editor"
        role="dialog"
        aria-modal="true"
        aria-labelledby="calendar-task-editor-title"
        onSubmit={(event) => onSave(event, value)}
      >
        <header>
          <div>
            <span>{value.id ? "Edit task" : "New task"}</span>
            <h2 id="calendar-task-editor-title">{value.id ? value.title || "Untitled task" : "Add a task"}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close task editor"><X size={19} /></button>
        </header>
        {error && <div className="calendar-conflict-warning"><AlertTriangle size={18} /><div><strong>{error.startsWith("Task saved,") ? "Google sync was not queued" : "Task could not be saved"}</strong><span>{error}</span></div></div>}
        {notice && <div className="calendar-task-save-notice" role="status">{notice}</div>}

        <label className="calendar-task-title-field">
          Title
          <input autoFocus required value={value.title} onChange={(event) => onChange("title", event.target.value)} placeholder="For example, call the supplier" />
        </label>

        <div className="calendar-form-grid calendar-task-basics">
          <label>Progress<select value={value.status} onChange={(event) => onChange("status", event.target.value)}><option value="todo">Not started</option><option value="in_progress">In progress</option><option value="blocked">Waiting on something</option><option value="done">Completed</option><option value="cancelled">Cancelled</option></select></label>
          <label>Priority<select value={value.priority} onChange={(event) => onChange("priority", event.target.value)}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label>
        </div>

        <section className="calendar-task-section">
          <div className="calendar-task-section-heading"><strong>Schedule</strong><small>Optional</small></div>
          <p>Leave these empty if you do not need to schedule the task yet.</p>
          <div className={`calendar-form-grid calendar-task-date-grid${includeEndTime ? " has-end" : ""}`}>
            <TaskDateTimeFields label="Start" value={value.scheduled_start} onChange={(nextValue) => onChange("scheduled_start", nextValue)} />
            {includeEndTime && <TaskDateTimeFields label="End" value={value.scheduled_end} onChange={(nextValue) => onChange("scheduled_end", nextValue)} />}
          </div>
          <label className="calendar-checkbox calendar-task-end-toggle">
            <input
              type="checkbox"
              checked={includeEndTime}
              onChange={(event) => {
                const checked = event.target.checked;
                setIncludeEndTime(checked);
                if (!checked) {
                  onChange("scheduled_end", "");
                } else if (!value.scheduled_end && value.scheduled_start) {
                  const suggestedEnd = new Date(new Date(value.scheduled_start).getTime() + 60 * 60 * 1000);
                  if (!Number.isNaN(suggestedEnd.getTime())) onChange("scheduled_end", localInputValue(suggestedEnd));
                }
              }}
            />
            <span>Add an end date and time</span>
          </label>
          <div className="calendar-form-grid">
            <label>Reminder<select value={value.reminder_minutes_before} onChange={(event) => onChange("reminder_minutes_before", event.target.value)}><option value="">No reminder</option><option value="0">At the start time</option><option value="5">5 minutes before</option><option value="10">10 minutes before</option><option value="15">15 minutes before</option><option value="30">30 minutes before</option><option value="60">1 hour before</option><option value="1440">1 day before</option></select></label>
            <label>Repeats<select value={value.repeat} onChange={(event) => onChange("repeat", event.target.value)}><option value="none">Does not repeat</option><option value="daily">Every day</option><option value="weekly">Every week</option><option value="monthly">Every month</option></select></label>
          </div>
          {(value.scheduled_start || value.scheduled_end) && (
            <div className="calendar-task-schedule-tools">
              <button
                type="button"
                disabled={saving}
                onClick={() => { onChange("scheduled_start", ""); onChange("scheduled_end", ""); setIncludeEndTime(false); }}
              >
                Clear scheduled time
              </button>
            </div>
          )}
        </section>


        <div className="calendar-modal-actions calendar-task-editor-actions">
          {value.id && <button type="button" className="is-archive" disabled={saving} onClick={onArchive}><Archive size={16} /> Archive</button>}
          {value.id && <button type="button" className="is-danger" disabled={saving} onClick={onDelete}><Trash2 size={16} /> Delete</button>}
          <span />
          <button type="button" disabled={saving} onClick={onClose}>Cancel</button>
          <button type="submit" className="is-primary" disabled={saving}>{saving ? "Saving…" : "Save task"}</button>
        </div>
      </form>
    </div>
  );
}

function AgendaTaskRow({ task, start, end, unscheduled = false, saving, onOpen, onArchive, onDelete }) {
  return (
    <div className="calendar-agenda-task-row">
      <button type="button" className={`calendar-agenda-task${unscheduled ? " is-unscheduled" : ""}`} onClick={() => onOpen(task)}>
        <time>{unscheduled ? <><ListTodo size={19} /><span>Task</span></> : <><strong>{new Date(start).getDate()}</strong><span>{new Date(start).toLocaleDateString(undefined, { month: "short", weekday: "short" })}</span></>}</time>
        <i />
        <div><strong>{task.title}</strong><span>{unscheduled ? (task.due_at ? `Due ${new Date(task.due_at).toLocaleString()}` : "Choose a time to place this task on your calendar") : <><ListTodo size={14} /> {formatTime(start)} - {formatTime(end)} - Scheduled task{task.recurrence_rule ? ` - Repeats ${task.recurrence_rule.replace("FREQ=", "").toLowerCase()}` : ""}</>}</span></div>
        <small>{task.status.replace("_", " ")}</small>
      </button>
      <div className="calendar-agenda-task-actions">
        <button type="button" className="calendar-agenda-archive" disabled={saving} onClick={() => onArchive(task)} aria-label={`Archive ${task.title}`} title="Archive task">
          <Archive size={15} />
          <span>Archive</span>
        </button>
        <button type="button" className="calendar-agenda-delete" disabled={saving} onClick={() => onDelete(task)} aria-label={`Delete ${task.title}`} title="Delete task">
          <Trash2 size={15} />
          <span>Delete</span>
        </button>
      </div>
    </div>
  );
}

function DateActionChooser({ date, onClose, onTask, onReservation, onOpenDay }) {
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const dateLabel = date.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="calendar-date-action-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="calendar-date-action" role="dialog" aria-modal="true" aria-labelledby="calendar-date-action-title">
        <header>
          <div><span>{dateLabel}</span><h2 id="calendar-date-action-title">What would you like to add?</h2></div>
          <button type="button" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </header>
        <div className="calendar-date-action-options">
          <button type="button" onClick={onTask}>
            <span className="is-task"><ListTodo size={21} /></span>
            <strong>Create task</strong>
            <small>Add work with a schedule, due date, and reminder.</small>
          </button>
          <button type="button" onClick={onReservation}>
            <span className="is-reservation"><CalendarDays size={21} /></span>
            <strong>Reserve time</strong>
            <small>Block this date for an event, meeting, or reservation.</small>
          </button>
        </div>
        <button type="button" className="calendar-date-open-day" onClick={onOpenDay}>Open day view</button>
      </section>
    </div>
  );
}

export default function ReservationCalendarPage({ user = null, initialView = "", onViewChange = null, standaloneAgenda = false }) {
  const [focusDate, setFocusDate] = useState(() => new Date());
  const [agendaDates, setAgendaDates] = useState(() => agendaDateRange());
  const [agendaDraft, setAgendaDraft] = useState(agendaDates);
  const [agendaPreset, setAgendaPreset] = useState("month");
  const [agendaFilterError, setAgendaFilterError] = useState("");
  const [agendaTaskStatus, setAgendaTaskStatus] = useState("open");
  const [agendaTaskStatusDraft, setAgendaTaskStatusDraft] = useState("open");
  const [view, setView] = useState(() => standaloneAgenda ? "agenda" : VIEWS.includes(initialView) ? initialView : phoneAgendaMatches() ? "month" : "week");
  const lastCalendarView = useRef(phoneAgendaMatches() ? "month" : "week");
  const [mobileToolsOpen, setMobileToolsOpen] = useState(false);
  const [workspace, setWorkspace] = useState({ calendars: [], events: [], tasks: [], connections: [] });
  const [enabledCalendars, setEnabledCalendars] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [editor, setEditor] = useState(null);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState("");
  const [history, setHistory] = useState([]);
  const [taskTitle, setTaskTitle] = useState("");
  const [showCalendarTasks, setShowCalendarTasks] = useState(true);
  const [taskSchedule, setTaskSchedule] = useState("");
  const [taskEditor, setTaskEditor] = useState(null);
  const [taskEditorError, setTaskEditorError] = useState("");
  const [taskEditorNotice, setTaskEditorNotice] = useState("");
  const [taskConfirmation, setTaskConfirmation] = useState(null);
  const [dateAction, setDateAction] = useState(null);
  const [connectionOperation, setConnectionOperation] = useState({ id: "", action: "" });
  const [connectionDirection, setConnectionDirection] = useState("read");
  const [expandedSidebarSections, setExpandedSidebarSections] = useState(() => new Set());
  const [rangeStart, rangeEnd] = useMemo(() => standaloneAgenda
    ? [new Date(`${agendaDates.from}T00:00:00`), addDays(new Date(`${agendaDates.to}T00:00:00`), 1)]
    : rangeForView(focusDate, view), [agendaDates, focusDate, standaloneAgenda, view]);
  const lastHandledRefreshRef = useRef(0);
  const lastVisibilityRefreshRef = useRef(0);
  const hasLoadedWorkspaceRef = useRef(false);
  const tenantScope = user?.tenant_id ?? user?.tenantId ?? "";
  const userScope = user?.id || user?.auth_id || user?.authId || "";
  const cacheIdentity = useMemo(
    () => ({ tenantScope: String(tenantScope), userScope: String(userScope) }),
    [tenantScope, userScope]
  );
  const calendarFeaturesAvailable = workspace.calendar_features_available !== false;
  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return undefined;
    const mediaQuery = window.matchMedia(PHONE_AGENDA_QUERY);
    const syncPhoneLayout = (event) => {
      const matches = typeof event?.matches === "boolean" ? event.matches : mediaQuery.matches;
      if (matches && !standaloneAgenda) {
        lastCalendarView.current = "month";
        setView((current) => CALENDAR_VIEWS.includes(current) ? "month" : current);
      }
    };
    syncPhoneLayout(mediaQuery);
    mediaQuery.addEventListener?.("change", syncPhoneLayout);
    mediaQuery.addListener?.(syncPhoneLayout);
    return () => {
      mediaQuery.removeEventListener?.("change", syncPhoneLayout);
      mediaQuery.removeListener?.(syncPhoneLayout);
    };
  }, [standaloneAgenda]);
  const toggleSidebarSection = (section) => setExpandedSidebarSections((current) => {
    const next = new Set(current);
    if (next.has(section)) next.delete(section);
    else next.add(section);
    return next;
  });
  const selectView = (nextView) => {
    if (CALENDAR_VIEWS.includes(nextView)) lastCalendarView.current = nextView;
    setView(nextView);
    onViewChange?.(nextView);
  };

  useEffect(() => {
    let active = true;
    const start = rangeStart.toISOString();
    const end = rangeEnd.toISOString();
    const cacheKey = createCalendarWorkspaceCacheKey({ ...cacheIdentity, start, end });
    const forceRefresh = refreshKey !== lastHandledRefreshRef.current;
    if (forceRefresh) {
      lastHandledRefreshRef.current = refreshKey;
      clearCalendarWorkspaceCache(cacheIdentity);
    }
    const cachedEntry = forceRefresh
      ? null
      : readCalendarWorkspaceCacheEntry(cacheKey, cacheIdentity);
    const cached = cachedEntry?.workspace || null;

    queueMicrotask(() => {
      if (!active) return;
      if (cached) {
        hasLoadedWorkspaceRef.current = true;
        setWorkspace(cached);
        setEnabledCalendars((current) => current.size ? current : new Set([...(cached.calendars || []).map((item) => item.id), "reservations"]));
        setError(cached.warning || "");
        setLoading(false);
      } else if (!hasLoadedWorkspaceRef.current) {
        setLoading(true);
      }
    });

    if (cachedEntry?.freshness === "fresh") {
      return () => { active = false; };
    }

    getOrCreateCalendarWorkspaceRequest(
      cacheKey,
      () => fetchCalendarWorkspace({ start, end, force: forceRefresh })
    )
      .then((data) => {
        if (!active) return;
        hasLoadedWorkspaceRef.current = true;
        writeCalendarWorkspaceCache(cacheKey, data, cacheIdentity);
        setWorkspace(data);
        setEnabledCalendars((current) => current.size ? current : new Set([...(data.calendars || []).map((item) => item.id), "reservations"]));
        setError(data.warning || "");
      })
      .catch((loadError) => active && setError(loadError?.message || "Calendar could not be loaded."))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [cacheIdentity, rangeEnd, rangeStart, refreshKey]);

  useEffect(() => {
    const refreshVisibleCalendar = () => {
      if (typeof document !== "undefined" && document.visibilityState === "hidden") return;
      const now = Date.now();
      if (now - lastVisibilityRefreshRef.current < 1000) return;
      lastVisibilityRefreshRef.current = now;
      setRefreshKey((value) => value + 1);
    };
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") refreshVisibleCalendar();
    };

    window.addEventListener("focus", refreshVisibleCalendar);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      window.removeEventListener("focus", refreshVisibleCalendar);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, []);

  useEffect(() => {
    const taskSyncPending = (workspace.tasks || []).some(
      (task) => task.sync_status === "pending"
    );
    const inboundSyncPending = (workspace.connections || []).some(
      (connection) => ["pending", "syncing"].includes(connection.inbound_sync_status)
    );
    if (!taskSyncPending && !inboundSyncPending) return undefined;
    const timer = window.setTimeout(
      () => setRefreshKey((value) => value + 1),
      5000
    );
    return () => window.clearTimeout(timer);
  }, [workspace.connections, workspace.tasks]);

  const calendarById = useMemo(() => new Map((workspace.calendars || []).map((item) => [item.id, item])), [workspace.calendars]);
  const visibleEvents = useMemo(
    () => (workspace.events || []).filter(
      (event) => event.source_type === "reservation" || enabledCalendars.has(event.calendar_id)
    ),
    [enabledCalendars, workspace.events]
  );
  const openTasks = useMemo(
    () => (workspace.tasks || []).filter(taskIsOpen),
    [workspace.tasks]
  );
  const agendaTasks = useMemo(
    () => (standaloneAgenda ? (workspace.tasks || []).filter((task) => !task.archived_at && task.status !== "cancelled" && (
      agendaTaskStatus === "all" || (agendaTaskStatus === "done" ? task.status === "done" : taskIsOpen(task))
    )) : showCalendarTasks ? openTasks : []).filter((task) => !task.calendar_id || enabledCalendars.has(task.calendar_id)),
    [agendaTaskStatus, enabledCalendars, openTasks, showCalendarTasks, standaloneAgenda, workspace.tasks]
  );
  const unscheduledAgendaTasks = useMemo(
    () => agendaTasks.filter((task) => !taskPlacementStart(task)),
    [agendaTasks]
  );
  const scheduledAgendaTasks = useMemo(
    () => expandTaskOccurrences(agendaTasks, rangeStart, rangeEnd),
    [agendaTasks, rangeEnd, rangeStart]
  );
  const visibleAgendaTaskCount = useMemo(
    () => new Set([...unscheduledAgendaTasks, ...scheduledAgendaTasks].map((task) => task.id)).size,
    [scheduledAgendaTasks, unscheduledAgendaTasks]
  );
  const agendaItems = useMemo(
    () => [
      ...visibleEvents.map((item) => ({ kind: "event", item, startsAt: item.starts_at })),
      ...scheduledAgendaTasks.map((item) => ({ kind: "task", item, startsAt: item.agenda_start })),
    ].sort((first, second) => new Date(first.startsAt) - new Date(second.startsAt)),
    [scheduledAgendaTasks, visibleEvents]
  );
  const visibleCalendarItems = useMemo(
    () => [
      ...visibleEvents.map((item) => ({
        kind: "event",
        item,
        key: `event-${item.id}`,
        startsAt: item.starts_at,
        endsAt: item.ends_at,
      })),
      ...scheduledAgendaTasks.map((item) => ({
        kind: "task",
        item,
        key: `task-${item.id}-${item.agenda_start}`,
        startsAt: item.agenda_start,
        endsAt: item.agenda_end,
      })),
    ],
    [scheduledAgendaTasks, visibleEvents]
  );
  const days = view === "day" ? [startOfDay(focusDate)] : Array.from({ length: 7 }, (_, index) => addDays(startOfWeek(focusDate), index));

  const openNewEvent = (date = focusDate, useSelectedTime = false) => {
    const defaultCalendar = workspace.calendars?.find((item) => item.is_default) || workspace.calendars?.[0];
    setHistory([]);
    setConflict("");
    setEditor(blankEditor(defaultCalendar?.id || "", date, workspace.viewer_timezone, useSelectedTime));
  };

  const openNewTask = (date = focusDate, useSelectedTime = false) => {
    const defaultCalendar = workspace.calendars?.find((item) => item.is_default) || workspace.calendars?.[0];
    if (!defaultCalendar) {
      setError("Choose or create a calendar before adding a task.");
      return;
    }
    setTaskEditorError("");
    setTaskEditorNotice("");
    setTaskEditor(blankTaskEditor(defaultCalendar.id, date, useSelectedTime));
  };

  const openDateActions = (date, useSelectedTime = false) => {
    setFocusDate(date);
    setDateAction({ date: new Date(date), useSelectedTime });
  };

  const openEvent = async (event) => {
    if (event.read_only) return;
    const baseId = event.series_id || event.id;
    setEditor(eventEditorValue({ ...event, id: baseId }));
    setConflict("");
    fetchCalendarEventHistory(baseId).then(setHistory).catch(() => setHistory([]));
  };

  const saveEvent = async (submitEvent) => {
    submitEvent.preventDefault();
    if (!calendarFeaturesAvailable || !editor?.calendar_id) return;
    let startsAt; let endsAt;
    try {
      startsAt = eventTimeToInstant(editor.starts_at, editor.timezone);
      endsAt = eventTimeToInstant(editor.ends_at, editor.timezone);
      if (endsAt <= startsAt) throw new Error("Choose an end time after the start time.");
    } catch (timeError) {
      setConflict(timeError.message); return;
    }
    setSaving(true);
    setConflict("");
    const payload = {
      calendar_id: editor.calendar_id, title: editor.title, description: editor.description,
      location: editor.location, starts_at: startsAt, ends_at: endsAt,
      timezone: editor.timezone, visibility: editor.visibility, transparency: editor.transparency,
      status: editor.status || "confirmed", all_day: false, recurrence_rule: recurrenceRule(editor.recurrence),
      attendees: [], reminders: [{ channel: "in_app", minutes_before: Number(editor.reminder) }],
      expected_version: editor.expected_version, allow_conflicts: editor.allow_conflicts,
    };
    try {
      if (editor.id) await updateCalendarEvent(editor.id, payload, editor.recurrence === "none" ? "event" : editor.recurrence_scope, editor.occurrence_start);
      else await createCalendarEvent(payload);
      setEditor(null);
      setRefreshKey((value) => value + 1);
    } catch (saveError) {
      const detail = saveError?.data?.detail || saveError?.detail;
      setConflict(detail?.message || saveError?.message || "The event could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const removeEvent = async () => {
    if (!editor?.id || !window.confirm("Delete this event? This action is recorded in event history.")) return;
    setSaving(true);
    try {
      await deleteCalendarEvent(editor.id, editor.expected_version, editor.recurrence === "none" ? "event" : editor.recurrence_scope, editor.occurrence_start);
      setEditor(null);
      setRefreshKey((value) => value + 1);
    } catch (removeError) {
      setConflict(removeError?.message || "The event could not be deleted.");
    } finally { setSaving(false); }
  };

  const addTask = async (event) => {
    event.preventDefault();
    if (!calendarFeaturesAvailable || !taskTitle.trim()) return;
    const defaultCalendar = workspace.calendars?.find((item) => item.is_default) || workspace.calendars?.[0];
    if (!defaultCalendar) {
      setError("Choose or create a calendar before adding a task.");
      return;
    }
    try {
      const scheduledStart = taskSchedule ? new Date(taskSchedule) : null;
      if (scheduledStart && Number.isNaN(scheduledStart.getTime())) {
        throw new Error("Choose a valid task date and time.");
      }
      await createCalendarTask({
        calendar_id: defaultCalendar.id,
        title: taskTitle.trim(),
        description: "",
        status: "todo",
        priority: "normal",
        due_at: null,
        scheduled_start: scheduledStart?.toISOString() || null,
        scheduled_end: null,
        reminder_minutes_before: scheduledStart ? 10 : null,
        recurrence_rule: null,
        milestone: false,
      });
      setTaskTitle("");
      setTaskSchedule("");
      setRefreshKey((value) => value + 1);
    } catch (taskError) { setError(taskError?.message || "Task could not be created."); }
  };

  const openTask = (task) => {
    setTaskEditorError("");
    setTaskEditorNotice("");
    setTaskEditor(taskEditorValue(task));
  };

  const saveTask = async (submitEvent, editedTask = taskEditor) => {
    submitEvent.preventDefault();
    if (!editedTask) return;
    setSaving(true);
    setTaskEditorError("");
    setTaskEditorNotice("");
    let optimisticId = "";
    let previousTask = null;
    let optimisticApplied = false;
    try {
      let scheduledStart = editedTask.scheduled_start ? new Date(editedTask.scheduled_start) : null;
      let scheduledEnd = editedTask.scheduled_end ? new Date(editedTask.scheduled_end) : null;
      if (!scheduledStart && scheduledEnd) throw new Error("Choose a scheduled start time first.");
      if (editedTask.repeat !== "none" && !scheduledStart) throw new Error("Choose a scheduled start time for a repeating task.");
      if (scheduledStart && scheduledEnd && scheduledEnd <= scheduledStart) throw new Error("Scheduled end must be after the start.");
      const taskPayload = {
        title: editedTask.title.trim(),
        description: editedTask.description || "",
        calendar_id: editedTask.calendar_id || null,
        project_id: editedTask.project_id || null,
        owner_user_id: editedTask.owner_user_id || null,
        status: editedTask.status,
        priority: editedTask.priority,
        estimate_minutes: editedTask.estimate_minutes ? Number(editedTask.estimate_minutes) : null,
        reminder_minutes_before: editedTask.reminder_minutes_before === "" ? null : Number(editedTask.reminder_minutes_before),
        due_at: editedTask.due_at ? new Date(editedTask.due_at).toISOString() : null,
        scheduled_start: scheduledStart?.toISOString() || null,
        scheduled_end: scheduledEnd?.toISOString() || null,
        recurrence_rule: recurrenceRule(editedTask.repeat),
        milestone: Boolean(editedTask.milestone),
      };
      optimisticId = editedTask.id || `optimistic-task-${Date.now()}`;
      previousTask = editedTask.id
        ? (workspace.tasks || []).find((task) => task.id === editedTask.id) || null
        : null;
      const optimisticTask = {
        ...editedTask,
        ...taskPayload,
        id: optimisticId,
        version: editedTask.id ? Number(editedTask.version || 0) + 1 : 1,
      };
      setWorkspace((current) => ({
        ...current,
        tasks: editedTask.id
          ? (current.tasks || []).map((task) => task.id === editedTask.id ? optimisticTask : task)
          : [...(current.tasks || []), optimisticTask],
      }));
      optimisticApplied = true;
      setTaskEditor(null);

      const savedTask = editedTask.id
        ? await updateCalendarTask(editedTask.id, taskPayload, editedTask.version)
        : await createCalendarTask(taskPayload);
      const savedTaskId = savedTask?.id || editedTask.id;
      setWorkspace((current) => ({
        ...current,
        tasks: (current.tasks || []).map((task) =>
          task.id === optimisticId ? { ...optimisticTask, ...(savedTask || {}), id: savedTaskId || optimisticId } : task
        ),
      }));
      clearCalendarWorkspaceCache(cacheIdentity);

      if (editedTask.sync_connection_id && !editedTask.is_synchronized) {
        syncCalendarTask(savedTaskId, editedTask.sync_connection_id)
          .then((syncedTask) => {
            if (syncedTask) {
              setWorkspace((current) => ({
                ...current,
                tasks: (current.tasks || []).map((task) => task.id === savedTaskId ? { ...task, ...syncedTask } : task),
              }));
            }
            clearCalendarWorkspaceCache(cacheIdentity);
          })
          .catch((syncError) => {
            setError(`Task saved, but Google synchronization could not be queued.${syncError?.message ? ` ${syncError.message}` : ""}`);
          });
      } else if (!editedTask.sync_connection_id && editedTask.is_synchronized) {
        unlinkCalendarTaskSync(editedTask.id)
          .then((unlinkedTask) => {
            if (unlinkedTask) {
              setWorkspace((current) => ({
                ...current,
                tasks: (current.tasks || []).map((task) => task.id === editedTask.id ? { ...task, ...unlinkedTask } : task),
              }));
            }
            clearCalendarWorkspaceCache(cacheIdentity);
          })
          .catch((syncError) => setError(syncError?.message || "Task saved, but Google Calendar could not be unlinked."));
      }
    } catch (taskError) {
      if (optimisticApplied) {
        setWorkspace((current) => ({
          ...current,
          tasks: editedTask.id
            ? (current.tasks || []).map((task) => task.id === optimisticId ? previousTask : task).filter(Boolean)
            : (current.tasks || []).filter((task) => task.id !== optimisticId),
        }));
      }
      setTaskEditor(editedTask);
      setTaskEditorError(taskError?.message || "The task could not be saved locally.");
    } finally {
      setSaving(false);
    }
  };

  const removeTask = async (selectedTask, mode = "local_only") => {
    if (!selectedTask?.id) return;
    setTaskConfirmation(null);
    setSaving(true);
    setTaskEditorError("");
    try {
      await deleteCalendarTask(selectedTask.id, mode);
      if (taskEditor?.id === selectedTask.id) setTaskEditor(null);
      setRefreshKey((value) => value + 1);
    } catch (taskError) {
      if (taskEditor?.id === selectedTask.id) setTaskEditorError(taskError?.message || "The task could not be deleted.");
      else setError(taskError?.message || "The task could not be deleted.");
    } finally {
      setSaving(false);
    }
  };

  const archiveTask = async (selectedTask) => {
    if (!selectedTask?.id) return;
    setTaskConfirmation(null);
    setSaving(true);
    setTaskEditorError("");
    try {
      await archiveCalendarTask(selectedTask.id, selectedTask.version);
      setTaskEditor(null);
      setRefreshKey((value) => value + 1);
    } catch (taskError) {
      setTaskEditorError(taskError?.message || "The task could not be archived.");
    } finally {
      setSaving(false);
    }
  };

  const requestTaskArchive = (selectedTask) => {
    if (selectedTask?.id) setTaskConfirmation({ action: "archive", task: selectedTask });
  };

  const requestTaskDelete = (selectedTask) => {
    if (selectedTask?.id) setTaskConfirmation({ action: "delete", task: selectedTask });
  };

  const connectProvider = async (provider) => {
    setConnectionOperation({ id: provider, action: "create" });
    try {
      const result = await createCalendarConnection({ provider, account_label: provider === "microsoft" ? "Outlook" : provider === "google" ? "Google Calendar" : "Calendar feed", direction: provider === "ics" ? "read" : connectionDirection });
      if (result.requires_oauth && result.connection?.id) {
        const url = await authorizeCalendarConnection(result.connection.id);
        if (url) window.location.assign(url);
      } else {
        setRefreshKey((value) => value + 1);
      }
    } catch (connectionError) { setError(connectionError?.message || "Connection could not be created."); }
    finally { setConnectionOperation({ id: "", action: "" }); }
  };

  const syncProvider = async (connection) => {
    setConnectionOperation({ id: connection.id, action: connection.status === "setup_required" ? "authorize" : "sync" });
    try {
      if (connection.status === "setup_required") {
        const url = await authorizeCalendarConnection(connection.id);
        if (url) window.location.assign(url);
        return;
      }
      await syncCalendarConnection(connection.id);
      setRefreshKey((value) => value + 1);
    } catch (syncError) {
      setError(syncError?.message || "Calendar sync failed. Open Sync health for details.");
    } finally {
      setConnectionOperation({ id: "", action: "" });
    }
  };

  const toggleInboundProvider = async (connection, enabled) => {
    setConnectionOperation({ id: connection.id, action: "inbound" });
    try {
      await setCalendarInboundSync(connection.id, enabled);
      setRefreshKey((value) => value + 1);
    } catch (syncError) {
      setError(syncError?.message || "Inbound calendar synchronization could not be updated.");
    } finally {
      setConnectionOperation({ id: "", action: "" });
    }
  };

  const upgradeProvider = async (connection) => {
    if (!confirmGoogleWriteUpgrade()) return;
    setConnectionOperation({ id: connection.id, action: "upgrade" });
    try {
      const url = await upgradeCalendarConnection(connection.id);
      if (url) window.location.assign(url);
    } catch (upgradeError) {
      setError(upgradeError?.message || "Google write access could not be requested.");
    } finally {
      setConnectionOperation({ id: "", action: "" });
    }
  };

  const removeConnection = async (connection) => {
    if (!confirmIncompleteConnectionRemoval()) return;
    setConnectionOperation({ id: connection.id, action: "remove" });
    try {
      await removeCalendarConnection(connection.id);
      setRefreshKey((value) => value + 1);
    } catch (removeError) {
      setError(removeError?.message || "Calendar connection could not be removed.");
    } finally {
      setConnectionOperation({ id: "", action: "" });
    }
  };

  const disconnectProvider = async (connection) => {
    if (!confirmConnectedAccountDisconnect()) return;
    setConnectionOperation({ id: connection.id, action: "disconnect" });
    try {
      await disconnectCalendarConnection(connection.id);
      setRefreshKey((value) => value + 1);
    } catch (disconnectError) {
      setError(disconnectError?.message || "Calendar account could not be disconnected.");
    } finally {
      setConnectionOperation({ id: "", action: "" });
    }
  };

  const movePeriod = (direction) => {
    const next = new Date(focusDate);
    if (view === "month") next.setMonth(next.getMonth() + direction);
    else next.setDate(next.getDate() + direction * (view === "day" ? 1 : view === "agenda" ? 31 : 7));
    setFocusDate(next);
  };

  const resolveInvitation = async (reviewId, disposition) => {
    try {
      await resolveCalendarInvitation(reviewId, disposition);
      setRefreshKey((value) => value + 1);
    } catch (reviewError) {
      setError(reviewError?.message || "Invitation review could not be updated.");
    }
  };

  const toggleCalendar = (id) => setEnabledCalendars((current) => {
    const next = new Set(current);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  return (
    <div className={`reservation-calendar-page calendar-workspace-page${standaloneAgenda ? " is-agenda-page" : ""}`}>
      {(loading) ? <PageHeaderSkeleton className="reservation-calendar-toolbar app-page-intro" actions={false} /> : (<header className="reservation-calendar-toolbar app-page-intro">
        <div className="calendar-toolbar-copy"><h1>{standaloneAgenda ? "My tasks" : "Calendar"}</h1><p>{standaloneAgenda ? "Manage your tasks and upcoming schedule." : "Bookings, events, tasks, reminders, and sync health in one place."}</p></div>
      </header>)}

      {!standaloneAgenda && <section className="calendar-summary-grid" aria-label="Calendar summary">
        <article><span>Calendars</span><strong>{(workspace.calendars?.length || 0) + 1}</strong></article>
        <article><span>Events in view</span><strong>{workspace.events?.length || 0}</strong></article>
        <article><span>Open tasks</span><strong>{openTasks.length}</strong></article>
        <article><span>Connections</span><strong>{workspace.connections?.length || 0}</strong></article>
      </section>}

      {standaloneAgenda ? <form className="agenda-filter-bar" aria-label="My tasks filters" onSubmit={(event) => {
        event.preventDefault();
        const start = new Date(`${agendaDraft.from}T00:00:00`);
        const end = addDays(new Date(`${agendaDraft.to}T00:00:00`), 1);
        if (!agendaDraft.from || !agendaDraft.to || !Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime()) || end <= start) {
          setAgendaFilterError("Choose an end date on or after the start date."); return;
        }
        if (end - start > 370 * 86400000) {
          setAgendaFilterError("Choose a date range of 370 days or less."); return;
        }
        setAgendaFilterError(""); setAgendaTaskStatus(agendaTaskStatusDraft); setAgendaDates((current) => current.from === agendaDraft.from && current.to === agendaDraft.to ? current : { ...agendaDraft });
      }}>
        <label>Date range<select aria-label="Date range" value={agendaPreset} onChange={(event) => {
          const preset = event.target.value; setAgendaPreset(preset); setAgendaFilterError("");
          if (preset !== "custom") setAgendaDraft(agendaDateRange(preset === "today" ? 1 : ["week", "last-week"].includes(preset) ? 7 : 30, preset.startsWith("last-")));
        }}><option value="month">Next 30 days</option><option value="today">Today</option><option value="week">Next 7 days</option><option value="last-week">Last 7 days</option><option value="last-month">Last 30 days</option><option value="custom">Custom dates</option></select></label>
        {agendaPreset === "custom" && <><label>From<DateTimeInput type="date" required value={agendaDraft.from} onChange={(event) => setAgendaDraft((current) => ({ ...current, from: event.target.value }))} /></label><label>To<DateTimeInput type="date" required value={agendaDraft.to} onChange={(event) => setAgendaDraft((current) => ({ ...current, to: event.target.value }))} /></label></>}
        <label>Task status<select aria-label="Task status" value={agendaTaskStatusDraft} onChange={(event) => setAgendaTaskStatusDraft(event.target.value)}><option value="open">Open tasks</option><option value="done">Completed tasks</option><option value="all">Open and completed</option></select></label>
        <button type="submit" className="agenda-filter-apply">Apply filters</button>
        <span className="agenda-filter-summary" aria-live="polite">Showing scheduled items {formatRange(rangeStart, rangeEnd)}. Unscheduled tasks stay visible.</span>
        {agendaFilterError && <p role="alert">{agendaFilterError}</p>}
      </form> : <div className="calendar-control-bar">
        {view === "reservations" ? <strong className="calendar-reservations-control-title">All reservation records</strong> : <>
          <button type="button" onClick={() => setFocusDate(new Date())}>Today</button>
          <button type="button" onClick={() => movePeriod(-1)} aria-label="Previous"><ChevronLeft size={18} /></button>
          <button type="button" onClick={() => movePeriod(1)} aria-label="Next"><ChevronRight size={18} /></button>
          <strong aria-live="polite">{view === "month" ? focusDate.toLocaleDateString(undefined, { month: "long", year: "numeric" }) : formatRange(rangeStart, rangeEnd)}</strong>
        </>}
        <span className="calendar-control-spacer" />
        {!standaloneAgenda && <div className="reservation-calendar-view-switch" role="group" aria-label="Calendar view">{CALENDAR_VIEWS.map((item) => <button type="button" className={view === item ? "is-active" : ""} aria-pressed={view === item} key={item} onClick={() => selectView(item)}>{item}</button>)}</div>}
      </div>}

      {error && !(standaloneAgenda && error === "Calendar features are disabled. Reservations remain available.") && <div className="calendar-workspace-notice"><AlertTriangle size={17} />{error}<button type="button" aria-label="Dismiss calendar notice" onClick={() => setError("")}><X size={15} /></button></div>}

      {!standaloneAgenda && <button type="button" className="calendar-mobile-tools-toggle" aria-expanded={mobileToolsOpen} aria-controls="calendar-workspace-tools" onClick={() => setMobileToolsOpen((open) => !open)}><CalendarDays size={16} />Calendar tools<ChevronDown size={16} /></button>}
      <div className="reservation-calendar-layout">
        {!standaloneAgenda && <aside id="calendar-workspace-tools" className={`reservation-calendar-sidebar calendar-workspace-sidebar${mobileToolsOpen ? " is-mobile-open" : ""}`}>
          <div className="calendar-sidebar-category"><span>My calendars</span></div>
          <section className="calendar-sidebar-group calendar-calendars-panel">
            <SidebarSectionHeading section="calendars" icon={<CalendarDays size={16} />} title="Calendars" subtitle="Choose what appears" count={(workspace.calendars?.length || 0) + 1} expanded={expandedSidebarSections.has("calendars")} onToggle={toggleSidebarSection} />
            {expandedSidebarSections.has("calendars") && <div id="calendar-sidebar-calendars" className="calendar-sidebar-card calendar-source-list">{(workspace.calendars || []).map((calendar) => <label className="calendar-source-toggle" key={calendar.id}><input type="checkbox" checked={enabledCalendars.has(calendar.id)} onChange={() => toggleCalendar(calendar.id)} /><i style={{ background: calendar.color }} /><span>{calendar.name}</span>{calendar.is_default && <small>Default</small>}</label>)}</div>}
            <label className="calendar-source-toggle calendar-tasks-source"><input type="checkbox" checked={showCalendarTasks} onChange={(event) => setShowCalendarTasks(event.target.checked)} /><ListTodo size={16} aria-hidden="true" /><span>My tasks</span><small>{openTasks.length}</small></label>
            <button type="button" className="calendar-new-event-link" onClick={() => openNewEvent()}><Plus size={16} aria-hidden="true" /><span>New event</span></button>
            <button type="button" className="calendar-reservations-link" aria-pressed={view === "reservations"} onClick={() => selectView("reservations")}><CalendarDays size={16} aria-hidden="true" /><span>Reservations</span><ChevronRight size={16} aria-hidden="true" /></button>
          </section>

          <div className="calendar-sidebar-category"><span>Planning</span></div>
          <section className="calendar-sidebar-group calendar-workload-panel">
            <SidebarSectionHeading section="workload" icon={<Clock3 size={16} />} title="Workload" subtitle="Team capacity" count={workspace.workload?.length || 0} expanded={expandedSidebarSections.has("workload")} onToggle={toggleSidebarSection} />
            {expandedSidebarSections.has("workload") && <div id="calendar-sidebar-workload" className="calendar-sidebar-section-content">{(workspace.workload || []).map((item) => <div className="calendar-workload-row" key={item.user_id || "unassigned"}><span>{item.user_id ? `Member ${item.user_id}` : "Unassigned"}</span><strong>{Math.round(item.estimate_minutes / 60 * 10) / 10}h</strong><div><i style={{ width: `${Math.min(100, item.estimate_minutes / 24)}%` }} /></div><small>{item.open_tasks} open tasks</small></div>)}</div>}
          </section>
          {(workspace.invitation_reviews || []).length > 0 && <section className="calendar-invitation-panel"><div className="calendar-section-title"><strong><ShieldCheck size={16} /> Invitation safety</strong><span>{workspace.invitation_reviews.length}</span></div>{workspace.invitation_reviews.slice(0, 4).map((review) => <div className="calendar-invitation-review" key={review.id}><strong>{review.sender_email}</strong><span>{(review.reasons || []).join(" · ").replaceAll("_", " ")}</span><div><button type="button" onClick={() => resolveInvitation(review.id, "allowed")}>Allow</button><button type="button" onClick={() => resolveInvitation(review.id, "blocked")}>Block</button><button type="button" onClick={() => resolveInvitation(review.id, "reported")}>Report</button></div></div>)}</section>}
          <div className="calendar-sidebar-category"><span>Connections</span></div>
          <section className="calendar-sidebar-group calendar-sync-panel">
            <SidebarSectionHeading section="sync" icon={<Link2 size={16} />} title="Sync health" subtitle="Connected accounts" count={workspace.connections?.length || 0} expanded={expandedSidebarSections.has("sync")} onToggle={toggleSidebarSection} />
            {expandedSidebarSections.has("sync") && <div id="calendar-sidebar-sync" className="calendar-connected-list">
              {(workspace.connections || []).length === 0 && <p className="calendar-no-connections">No calendars connected yet.</p>}
              {(workspace.connections || []).map((connection) => <CalendarConnectionCard key={connection.id} connection={connection} operation={connectionOperation.id === connection.id ? connectionOperation.action : ""} onAuthorize={syncProvider} onSync={syncProvider} onInboundToggle={toggleInboundProvider} onUpgrade={upgradeProvider} onRemove={removeConnection} onDisconnect={disconnectProvider} />)}
            </div>}
            <div className="calendar-new-connection"><button type="button" className="calendar-new-connection-toggle" aria-expanded={expandedSidebarSections.has("connect")} aria-controls="calendar-sidebar-connect" onClick={() => toggleSidebarSection("connect")}><span className="calendar-new-connection-heading"><strong>Add an account</strong><small>Connect securely with OAuth 2.0</small></span><ChevronDown className="calendar-sidebar-chevron" size={15} /></button>{expandedSidebarSections.has("connect") && <div id="calendar-sidebar-connect" className="calendar-sidebar-section-content"><label className="calendar-sync-direction"><span>Access</span><select value={connectionDirection} onChange={(event) => setConnectionDirection(event.target.value)} disabled={!calendarFeaturesAvailable}><option value="read">Read only</option><option value="two_way">Two-way sync</option></select></label><div className="calendar-connect-actions"><button type="button" disabled={!calendarFeaturesAvailable || Boolean(connectionOperation.id)} onClick={() => connectProvider("google")}>Google</button><button type="button" disabled={!calendarFeaturesAvailable || Boolean(connectionOperation.id)} onClick={() => connectProvider("microsoft")}>Outlook</button><button type="button" disabled={!calendarFeaturesAvailable || Boolean(connectionOperation.id)} onClick={() => connectProvider("ics")}>ICS</button></div><small className="calendar-connection-help">Google and Outlook open a secure sign-in. ICS imports a calendar feed.</small></div>}</div>
          </section>
          <div className="calendar-privacy-note"><ShieldCheck size={17} /><span><strong>Privacy is explicit</strong>Each event shows its calendar and visibility.</span></div>
        </aside>}

        <main className={`reservation-calendar-surface calendar-workspace-surface is-${view}`}>
          {loading && <div className="reservation-calendar-loading">Loading calendar…</div>}
          {!loading && !standaloneAgenda && CALENDAR_VIEWS.includes(view) && unscheduledAgendaTasks.length > 0 && <section className="calendar-unscheduled-tasks" aria-labelledby="calendar-unscheduled-title">
            <header><h2 id="calendar-unscheduled-title">Tasks to schedule</h2><span>{unscheduledAgendaTasks.length}</span></header>
            <p>These tasks don’t have a date yet. Select one to add a date and time.</p>
            <div>{unscheduledAgendaTasks.map((task) => <button type="button" key={task.id} onClick={() => openTask(task)}><ListTodo size={15} aria-hidden="true" /><span>{task.title}</span><ChevronRight size={15} aria-hidden="true" /></button>)}</div>
          </section>}
          {!loading && (view === "day" || view === "week") && <div className={`calendar-time-grid is-${view}`}><div className="calendar-grid-header"><span>{Intl.DateTimeFormat().resolvedOptions().timeZone || "Local time"}</span>{days.map((day) => <button type="button" key={dateKey(day)} className={sameDay(day, new Date()) ? "is-today" : ""} onClick={() => { setFocusDate(day); setView("day"); }}><small>{day.toLocaleDateString(undefined, { weekday: "short" })}</small><strong>{day.getDate()}</strong></button>)}</div><div className="calendar-grid-body"><div className="calendar-grid-hours">{HOURS.map((hour) => <span key={hour}>{new Date(2026, 0, 1, hour).toLocaleTimeString([], { hour: "numeric" })}</span>)}</div>{days.map((day) => <div className="calendar-grid-day" key={dateKey(day)}>{HOURS.map((hour) => { const slot = new Date(day); slot.setHours(hour, 0, 0, 0); return <button type="button" className="calendar-grid-slot" key={hour} aria-label={`Add to ${slot.toLocaleString([], { weekday: "long", month: "long", day: "numeric", hour: "numeric" })}`} onClick={() => openDateActions(slot, true)} />; })}{visibleCalendarItems.filter((entry) => sameDay(entry.startsAt, day)).map((entry) => { const { item } = entry; const start = new Date(entry.startsAt); const end = new Date(entry.endsAt); const top = (start.getHours() + start.getMinutes() / 60) * 48; const height = Math.max(34, Math.min(180, (end - start) / 3600000 * 48)); const calendar = calendarById.get(item.calendar_id); return <button type="button" key={entry.key} className={`calendar-grid-event is-${entry.kind === "task" ? "task" : item.source_type || "madar"}`} style={{ top, height, "--event-color": calendar?.color || "var(--theme-primary)" }} onClick={() => entry.kind === "task" ? openTask(item) : openEvent(item)}><strong>{item.title}</strong><span>{formatTime(entry.startsAt)} · {entry.kind === "task" ? "Task" : calendar?.name || item.source_label}</span>{entry.kind === "task" ? <small>{item.status.replace("_", " ")}</small> : item.visibility && <small>{item.visibility.replace("calendar_default", "default privacy")}</small>}</button>; })}</div>)}</div></div>}
          {!loading && view === "month" && <div className="calendar-month-view"><div className="calendar-month-weekdays">{Array.from({ length: 7 }, (_, index) => addDays(rangeStart, index)).map((day) => <span key={day.getDay()}>{day.toLocaleDateString(undefined, { weekday: "short" })}</span>)}</div><div className="calendar-month-grid">{Array.from({ length: 42 }, (_, index) => addDays(rangeStart, index)).map((day) => { const dayItems = visibleCalendarItems.filter((entry) => sameDay(entry.startsAt, day)); return <section key={dateKey(day)} className={`${day.getMonth() !== focusDate.getMonth() ? "is-outside" : ""}${sameDay(day, new Date()) ? " is-today" : ""}`}><button type="button" aria-label={`Add to ${day.toLocaleDateString()}`} onClick={() => openDateActions(day)}>{day.getDate()}</button>{dayItems.slice(0, 4).map((entry) => <button type="button" className={`calendar-month-event${entry.kind === "task" ? " is-task" : ""}`} style={{ "--event-color": calendarById.get(entry.item.calendar_id)?.color || "var(--theme-primary)" }} key={entry.key} onClick={() => entry.kind === "task" ? openTask(entry.item) : openEvent(entry.item)}><span>{formatTime(entry.startsAt)}</span>{entry.kind === "task" && <ListTodo size={12} aria-hidden="true" />}{entry.item.title}</button>)}{dayItems.length > 4 && <small>+{dayItems.length - 4} more</small>}</section>; })}</div></div>}
          {!loading && view === "agenda" && <div className="calendar-agenda">
            <section className="calendar-agenda-create" aria-labelledby="calendar-agenda-title">
              <div><h2 id="calendar-agenda-title">{standaloneAgenda ? "Tasks" : "Agenda"}</h2><p>{standaloneAgenda ? `${visibleAgendaTaskCount} tasks in this view` : "Your events and tasks, in one place."}</p></div>
              <form className="calendar-agenda-task-form" onSubmit={addTask}>
                <label className="calendar-agenda-task-title"><span>New task</span><input value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} placeholder="What needs to be done?" aria-label="Task title" /></label>
                <div className="calendar-agenda-task-schedule"><label htmlFor="agenda-task-schedule">Date and time (optional)</label><AgendaDateTimePicker value={taskSchedule} onChange={setTaskSchedule} /></div>
                <button type="submit" disabled={!calendarFeaturesAvailable || !taskTitle.trim() || saving}><Plus size={16} />Add task</button>
              </form>
              {!calendarFeaturesAvailable && <p className="calendar-task-unavailable" role="status">You can draft a task here. Saving is unavailable while task services are disabled.</p>}
            </section>
            {unscheduledAgendaTasks.length > 0 && <><div className="calendar-agenda-section-title"><ListTodo size={15} /><strong>Unscheduled tasks</strong><span>{unscheduledAgendaTasks.length}</span></div>{unscheduledAgendaTasks.map((task) => <AgendaTaskRow key={`task-${task.id}`} task={task} unscheduled saving={saving} onOpen={openTask} onArchive={requestTaskArchive} onDelete={requestTaskDelete} />)}</>}
            {agendaItems.length > 0 && <div className="calendar-agenda-section-title"><CalendarDays size={15} /><strong>Schedule</strong><span>{agendaItems.length}</span></div>}
            {agendaItems.map(({ kind, item }) => {
              if (kind === "task") return <AgendaTaskRow key={`task-${item.id}-${item.agenda_start}`} task={item} start={item.agenda_start} end={item.agenda_end} saving={saving} onOpen={openTask} onArchive={requestTaskArchive} onDelete={requestTaskDelete} />;
              if (kind === "task") return <button type="button" className="calendar-agenda-task" key={`task-${item.id}-${item.agenda_start}`} onClick={() => openTask(item)}><time><strong>{new Date(item.agenda_start).getDate()}</strong><span>{new Date(item.agenda_start).toLocaleDateString(undefined, { month: "short", weekday: "short" })}</span></time><i /><div><strong>{item.title}</strong><span><ListTodo size={14} /> {formatTime(item.agenda_start)}–{formatTime(item.agenda_end)} · Scheduled task{item.recurrence_rule ? ` · Repeats ${item.recurrence_rule.replace("FREQ=", "").toLowerCase()}` : ""}</span></div><small>{item.status.replace("_", " ")}</small></button>;
              const calendar = calendarById.get(item.calendar_id);
              return <button type="button" key={`event-${item.id}`} onClick={() => openEvent(item)}><time><strong>{new Date(item.starts_at).getDate()}</strong><span>{new Date(item.starts_at).toLocaleDateString(undefined, { month: "short", weekday: "short" })}</span></time><i style={{ background: calendar?.color || "var(--theme-primary)" }} /><div><strong>{item.title}</strong><span><Clock3 size={14} /> {formatTime(item.starts_at)}–{formatTime(item.ends_at)} · {calendar?.name || item.source_label}</span></div><small>{item.read_only ? "Synced reservation" : item.visibility?.replace("calendar_default", "Default privacy")}</small></button>;
            })}
            {unscheduledAgendaTasks.length === 0 && agendaItems.length === 0 && <div className="reservation-calendar-empty"><CalendarDays size={30} /><strong>No events or tasks in this range</strong></div>}
          </div>}
          {view === "reservations" && <><div className="calendar-reservations-navigation"><button type="button" className="calendar-toolbar-action" onClick={() => selectView(lastCalendarView.current)}><ChevronLeft size={16} aria-hidden="true" />Back to calendar</button></div><CalendarReservationsTable /></>}
        </main>
      </div>

      {editor && <EventEditor value={editor} calendars={workspace.calendars || []} saving={saving} conflict={conflict} unavailableReason={!calendarFeaturesAvailable ? "You can draft an event here. Saving is unavailable while Calendar services are disabled." : !editor.calendar_id ? "Your Madar calendar is not ready yet. You can draft an event here, but saving is unavailable." : ""} onChange={(field, value) => setEditor((current) => ({ ...current, [field]: value }))} onClose={() => setEditor(null)} onSave={saveEvent} onDelete={removeEvent} />}
      {taskEditor && <TaskEditor value={taskEditor} saving={saving} error={taskEditorError} notice={taskEditorNotice} onClose={() => setTaskEditor(null)} onSave={saveTask} onArchive={() => requestTaskArchive(taskEditor)} onDelete={() => requestTaskDelete(taskEditor)} />}
      {taskConfirmation && (
        <div className={`calendar-task-confirmation is-${taskConfirmation.action}`}>
          <PageDeleteConfirmModal
            icon={taskConfirmation.action === "archive" ? <Archive size={24} /> : <AlertTriangle size={24} />}
            title={taskConfirmation.action === "archive" ? "Archive this task?" : "Delete this task?"}
            message={taskConfirmation.action === "archive"
              ? <><strong>"{taskConfirmation.task.title}"</strong> will leave the active Calendar and can be viewed in Archive.</>
              : taskConfirmation.task.is_synchronized
                ? <><strong>"{taskConfirmation.task.title}"</strong> is synchronized with Google Calendar. Choose where it should be deleted.</>
                : <><strong>"{taskConfirmation.task.title}"</strong> will be permanently deleted from Madar.</>}
            cancelLabel="Cancel"
            alternateLabel={taskConfirmation.action === "delete" && taskConfirmation.task.is_synchronized ? "Madar only" : undefined}
            confirmLabel={taskConfirmation.action === "archive" ? "Archive task" : taskConfirmation.task.is_synchronized ? "Madar + Google" : "Delete task"}
            confirmDisabled={saving}
            onCancel={() => setTaskConfirmation(null)}
            onAlternate={() => removeTask(taskConfirmation.task, "local_only")}
            onConfirm={() => taskConfirmation.action === "archive"
              ? archiveTask(taskConfirmation.task)
              : removeTask(taskConfirmation.task, taskConfirmation.task.is_synchronized ? "local_and_provider" : "local_only")}
          />
        </div>
      )}
      {dateAction && <DateActionChooser date={dateAction.date} onClose={() => setDateAction(null)} onTask={() => { const selection = dateAction; setDateAction(null); openNewTask(selection.date, selection.useSelectedTime); }} onReservation={() => { const selection = dateAction; setDateAction(null); openNewEvent(selection.date, selection.useSelectedTime); }} onOpenDay={() => { setFocusDate(dateAction.date); setView("day"); setDateAction(null); }} />}
      {editor?.id && history.length > 0 && <aside className="calendar-history-drawer"><header><History size={17} /><strong>Change history</strong></header>{history.slice(0, 8).map((item) => <div key={item.id}><strong>{item.action}</strong><span>{new Date(item.created_at).toLocaleString()} · {item.scope}</span></div>)}</aside>}
    </div>
  );
}
