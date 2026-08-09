import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Download,
  History,
  Link2,
  ListTodo,
  Plus,
  RefreshCw,
  ShieldCheck,
  Trash2,
  X,
} from "lucide-react";

import {
  createCalendarConnection,
  authorizeCalendarConnection,
  createCalendarEvent,
  createCalendarTask,
  deleteCalendarTask,
  deleteCalendarEvent,
  disconnectCalendarConnection,
  fetchCalendarEventHistory,
  fetchCalendarWorkspace,
  getCalendarExportUrl,
  importCalendarIcs,
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
  chooseTaskDeletionMode,
} from "./utils/calendarConnectionPrompts";
import {
  expandTaskOccurrences,
  taskIsOpen,
  taskPlacementStart,
} from "./utils/calendarTaskSchedule";

const HOURS = Array.from({ length: 24 }, (_, index) => index);
const VIEWS = ["day", "week", "month", "agenda"];
const pad = (value) => String(value).padStart(2, "0");

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
  return {
    id: "",
    calendar_id: calendarId,
    title: "",
    description: "",
    location: "",
    starts_at: localInputValue(start),
    ends_at: localInputValue(end),
    timezone: timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
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
    starts_at: localInputValue(event.starts_at),
    ends_at: localInputValue(event.ends_at),
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
  const end = new Date(start.getTime() + 60 * 60 * 1000);
  return taskEditorValue({
    id: "",
    calendar_id: calendarId,
    title: "",
    description: "",
    status: "todo",
    priority: "normal",
    scheduled_start: start.toISOString(),
    scheduled_end: end.toISOString(),
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

function EventEditor({ value, calendars, saving, conflict, onChange, onClose, onSave, onDelete }) {
  return (
    <div className="calendar-modal-backdrop" role="presentation">
      <form className="calendar-modal" onSubmit={onSave}>
        <header>
          <div>
            <span>{value.id ? "Edit event" : "New event"}</span>
            <h2>{value.id ? value.title || "Untitled event" : "Add to calendar"}</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close"><X size={19} /></button>
        </header>
        {conflict && (
          <div className="calendar-conflict-warning">
            <AlertTriangle size={18} />
            <div><strong>Time conflict</strong><span>{conflict}</span></div>
          </div>
        )}
        <label>Title<input autoFocus required value={value.title} onChange={(event) => onChange("title", event.target.value)} /></label>
        <div className="calendar-form-grid">
          <label>Starts<input required type="datetime-local" value={value.starts_at} onChange={(event) => onChange("starts_at", event.target.value)} /></label>
          <label>Ends<input required type="datetime-local" value={value.ends_at} onChange={(event) => onChange("ends_at", event.target.value)} /></label>
          <label>Calendar<select value={value.calendar_id} onChange={(event) => onChange("calendar_id", event.target.value)}>{calendars.map((calendar) => <option key={calendar.id} value={calendar.id}>{calendar.name}</option>)}</select></label>
          <label>Timezone<input value={value.timezone} onChange={(event) => onChange("timezone", event.target.value)} /></label>
          <label>Repeat<select value={value.recurrence} onChange={(event) => onChange("recurrence", event.target.value)}><option value="none">Does not repeat</option><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select></label>
          <label>Reminder<select value={value.reminder} onChange={(event) => onChange("reminder", event.target.value)}><option value="0">At start</option><option value="10">10 minutes before</option><option value="15">15 minutes before</option><option value="60">1 hour before</option><option value="1440">1 day before</option></select></label>
          <label>Privacy<select value={value.visibility} onChange={(event) => onChange("visibility", event.target.value)}><option value="calendar_default">Calendar default</option><option value="private">Private</option><option value="team">Team</option><option value="organization">Organization</option><option value="public">Public</option></select></label>
          <label>Availability<select value={value.transparency} onChange={(event) => onChange("transparency", event.target.value)}><option value="busy">Busy</option><option value="free">Free</option></select></label>
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
        <div className="calendar-modal-actions">
          {value.id && <button type="button" className="is-danger" onClick={onDelete}><Trash2 size={16} /> Delete</button>}
          <span />
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="submit" className="is-primary" disabled={saving}>{saving ? "Saving…" : "Save event"}</button>
        </div>
      </form>
    </div>
  );
}

function TaskEditor({ value, connections, saving, error, notice, onChange, onClose, onSave, onDelete }) {
  const writableGoogleConnections = connections.filter(
    (connection) =>
      connection.provider === "google"
      && connection.direction === "two_way"
      && ["connected", "degraded"].includes(connection.status)
  );
  const hasReadOnlyGoogle = connections.some(
    (connection) =>
      connection.provider === "google"
      && connection.direction === "read"
      && ["connected", "degraded"].includes(connection.status)
  );
  return (
    <div className="calendar-modal-backdrop" role="presentation">
      <form className="calendar-modal calendar-task-editor" onSubmit={onSave}>
        <header>
          <div><span>{value.id ? "Edit task" : "New task"}</span><h2>{value.id ? value.title || "Untitled task" : "Add a task"}</h2></div>
          <button type="button" onClick={onClose} aria-label="Close"><X size={19} /></button>
        </header>
        {error && <div className="calendar-conflict-warning"><AlertTriangle size={18} /><div><strong>{error.startsWith("Task saved,") ? "Google sync was not queued" : "Task could not be saved"}</strong><span>{error}</span></div></div>}
        {notice && <div className="calendar-task-save-notice" role="status">{notice}</div>}
        <label>Title<input autoFocus required value={value.title} onChange={(event) => onChange("title", event.target.value)} /></label>
        <div className="calendar-form-grid">
          <label>Status<select value={value.status} onChange={(event) => onChange("status", event.target.value)}><option value="todo">Todo</option><option value="in_progress">In progress</option><option value="blocked">Blocked</option><option value="done">Done</option><option value="cancelled">Cancelled</option></select></label>
          <label>Priority<select value={value.priority} onChange={(event) => onChange("priority", event.target.value)}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></label>
          <label>Scheduled start<input type="datetime-local" value={value.scheduled_start} onChange={(event) => onChange("scheduled_start", event.target.value)} /></label>
          <label>Scheduled end<input type="datetime-local" value={value.scheduled_end} onChange={(event) => onChange("scheduled_end", event.target.value)} /></label>
          <label>Due date<input type="datetime-local" value={value.due_at} onChange={(event) => onChange("due_at", event.target.value)} /></label>
          <label>Estimate (minutes)<input type="number" min="1" max="525600" value={value.estimate_minutes} onChange={(event) => onChange("estimate_minutes", event.target.value)} /></label>
          <label>Remind me before<select value={value.reminder_minutes_before} onChange={(event) => onChange("reminder_minutes_before", event.target.value)}><option value="">No reminder</option><option value="0">At start time</option><option value="5">5 minutes before</option><option value="10">10 minutes before</option><option value="15">15 minutes before</option><option value="30">30 minutes before</option><option value="60">1 hour before</option><option value="1440">1 day before</option></select></label>
          <label>Repeat<select value={value.repeat} onChange={(event) => onChange("repeat", event.target.value)}><option value="none">Does not repeat</option><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select></label>
          <label>Calendar sync<select value={value.sync_connection_id} onChange={(event) => onChange("sync_connection_id", event.target.value)}><option value="">Madar only</option>{writableGoogleConnections.map((connection) => <option key={connection.id} value={connection.id}>Sync to {connection.account_label || "Google Calendar"}</option>)}</select></label>
        </div>
        {hasReadOnlyGoogle && writableGoogleConnections.length === 0 && <p className="calendar-task-sync-help">Your Google connection is read only. Enable write access from Sync health to send scheduled tasks to Google Calendar.</p>}
        {value.sync_status && value.sync_status !== "not_synced" && <p className={`calendar-task-sync-status is-${value.sync_status}`}>Google sync: {value.sync_status.replaceAll("_", " ")}</p>}
        <label>Notes<textarea rows="3" value={value.description} onChange={(event) => onChange("description", event.target.value)} /></label>
        <div className="calendar-modal-actions">
          {value.id && <button type="button" className="is-danger" disabled={saving} onClick={onDelete}><Trash2 size={16} /> Delete</button>}
          <span />
          <button type="button" onClick={() => { onChange("scheduled_start", ""); onChange("scheduled_end", ""); }}>Clear schedule</button>
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="submit" className="is-primary" disabled={saving}>{saving ? "Saving…" : "Save task"}</button>
        </div>
      </form>
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

export default function ReservationCalendarPage({ user = null }) {
  const [focusDate, setFocusDate] = useState(() => new Date());
  const [view, setView] = useState("week");
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
  const [taskSchedule, setTaskSchedule] = useState("");
  const [taskEditor, setTaskEditor] = useState(null);
  const [taskEditorError, setTaskEditorError] = useState("");
  const [taskEditorNotice, setTaskEditorNotice] = useState("");
  const [dateAction, setDateAction] = useState(null);
  const [connectionOperation, setConnectionOperation] = useState({ id: "", action: "" });
  const [connectionDirection, setConnectionDirection] = useState("read");
  const [expandedSidebarSections, setExpandedSidebarSections] = useState(() => new Set());
  const [rangeStart, rangeEnd] = useMemo(() => rangeForView(focusDate, view), [focusDate, view]);
  const lastHandledRefreshRef = useRef(0);
  const tenantScope = user?.tenant_id ?? user?.tenantId ?? "";
  const userScope = user?.id || user?.auth_id || user?.authId || "";
  const cacheIdentity = useMemo(
    () => ({ tenantScope: String(tenantScope), userScope: String(userScope) }),
    [tenantScope, userScope]
  );
  const calendarFeaturesAvailable = workspace.calendar_features_available !== false;
  const toggleSidebarSection = (section) => setExpandedSidebarSections((current) => {
    const next = new Set(current);
    if (next.has(section)) next.delete(section);
    else next.add(section);
    return next;
  });
  const warmAgendaCache = useCallback(() => {
    const [agendaStart, agendaEnd] = rangeForView(focusDate, "agenda");
    const start = agendaStart.toISOString();
    const end = agendaEnd.toISOString();
    const cacheKey = createCalendarWorkspaceCacheKey({ ...cacheIdentity, start, end });
    if (readCalendarWorkspaceCacheEntry(cacheKey, cacheIdentity)) return;
    getOrCreateCalendarWorkspaceRequest(
      cacheKey,
      () => fetchCalendarWorkspace({ start, end })
    )
      .then((data) => writeCalendarWorkspaceCache(cacheKey, data, cacheIdentity))
      .catch(() => {
        // The normal view loader reports errors if the user opens Agenda.
      });
  }, [cacheIdentity, focusDate]);

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
        setWorkspace(cached);
        setEnabledCalendars((current) => current.size ? current : new Set([...(cached.calendars || []).map((item) => item.id), "reservations"]));
        setError(cached.warning || "");
        setLoading(false);
      } else {
        setLoading(true);
      }
    });

    if (cachedEntry?.freshness === "fresh") return () => { active = false; };

    getOrCreateCalendarWorkspaceRequest(
      cacheKey,
      () => fetchCalendarWorkspace({ start, end, force: forceRefresh })
    )
      .then((data) => {
        if (!active) return;
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
    () => (workspace.events || []).filter((event) => enabledCalendars.has(event.calendar_id)),
    [enabledCalendars, workspace.events]
  );
  const openTasks = useMemo(
    () => (workspace.tasks || []).filter(taskIsOpen),
    [workspace.tasks]
  );
  const agendaTasks = useMemo(
    () => openTasks.filter((task) => !task.calendar_id || enabledCalendars.has(task.calendar_id)),
    [enabledCalendars, openTasks]
  );
  const unscheduledAgendaTasks = useMemo(
    () => agendaTasks.filter((task) => !taskPlacementStart(task)),
    [agendaTasks]
  );
  const scheduledAgendaTasks = useMemo(
    () => expandTaskOccurrences(agendaTasks, rangeStart, rangeEnd),
    [agendaTasks, rangeEnd, rangeStart]
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
    if (!defaultCalendar) {
      setError("Choose or create a calendar before reserving time.");
      return;
    }
    setHistory([]);
    setConflict("");
    setEditor(blankEditor(defaultCalendar.id, date, workspace.viewer_timezone, useSelectedTime));
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
    setSaving(true);
    setConflict("");
    const payload = {
      calendar_id: editor.calendar_id, title: editor.title, description: editor.description,
      location: editor.location, starts_at: new Date(editor.starts_at).toISOString(), ends_at: new Date(editor.ends_at).toISOString(),
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
    if (!taskTitle.trim()) return;
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
      const scheduledEnd = scheduledStart
        ? new Date(scheduledStart.getTime() + 60 * 60 * 1000)
        : null;
      await createCalendarTask({
        calendar_id: defaultCalendar.id,
        title: taskTitle.trim(),
        description: "",
        status: "todo",
        priority: "normal",
        due_at: null,
        scheduled_start: scheduledStart?.toISOString() || null,
        scheduled_end: scheduledEnd?.toISOString() || null,
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

  const saveTask = async (submitEvent) => {
    submitEvent.preventDefault();
    if (!taskEditor) return;
    setSaving(true);
    setTaskEditorError("");
    setTaskEditorNotice("");
    try {
      let scheduledStart = taskEditor.scheduled_start ? new Date(taskEditor.scheduled_start) : null;
      let scheduledEnd = taskEditor.scheduled_end ? new Date(taskEditor.scheduled_end) : null;
      if (!scheduledStart && scheduledEnd) throw new Error("Choose a scheduled start time first.");
      if (taskEditor.repeat !== "none" && !scheduledStart) throw new Error("Choose a scheduled start time for a repeating task.");
      if (scheduledStart && !scheduledEnd) scheduledEnd = new Date(scheduledStart.getTime() + Number(taskEditor.estimate_minutes || 60) * 60000);
      if (scheduledStart && scheduledEnd <= scheduledStart) throw new Error("Scheduled end must be after the start.");
      const taskPayload = {
        title: taskEditor.title.trim(),
        description: taskEditor.description || "",
        calendar_id: taskEditor.calendar_id || null,
        project_id: taskEditor.project_id || null,
        owner_user_id: taskEditor.owner_user_id || null,
        status: taskEditor.status,
        priority: taskEditor.priority,
        estimate_minutes: taskEditor.estimate_minutes ? Number(taskEditor.estimate_minutes) : null,
        reminder_minutes_before: taskEditor.reminder_minutes_before === "" ? null : Number(taskEditor.reminder_minutes_before),
        due_at: taskEditor.due_at ? new Date(taskEditor.due_at).toISOString() : null,
        scheduled_start: scheduledStart?.toISOString() || null,
        scheduled_end: scheduledEnd?.toISOString() || null,
        recurrence_rule: recurrenceRule(taskEditor.repeat),
        milestone: Boolean(taskEditor.milestone),
      };
      const savedTask = taskEditor.id
        ? await updateCalendarTask(taskEditor.id, taskPayload, taskEditor.version)
        : await createCalendarTask(taskPayload);
      const savedTaskId = savedTask?.id || taskEditor.id;
      setTaskEditor((current) => ({
        ...current,
        ...taskEditorValue(savedTask || current),
      }));
      setTaskEditorNotice("Saved locally.");
      if (taskEditor.sync_connection_id && !taskEditor.is_synchronized) {
        try {
          await syncCalendarTask(savedTaskId, taskEditor.sync_connection_id);
          setTaskEditorNotice("Saved locally. Google sync queued.");
        } catch (syncError) {
          setTaskEditorError(
            `Task saved, but Google synchronization could not be queued.${syncError?.message ? ` ${syncError.message}` : ""}`
          );
          setRefreshKey((value) => value + 1);
          return;
        }
      } else if (!taskEditor.sync_connection_id && taskEditor.is_synchronized) {
        await unlinkCalendarTaskSync(taskEditor.id);
      }
      setTaskEditor(null);
      setRefreshKey((value) => value + 1);
    } catch (taskError) {
      setTaskEditorError(taskError?.message || "The task could not be saved locally.");
    } finally {
      setSaving(false);
    }
  };

  const removeTask = async () => {
    if (!taskEditor?.id) return;
    const mode = chooseTaskDeletionMode(Boolean(taskEditor.is_synchronized));
    if (!mode) return;
    setSaving(true);
    setTaskEditorError("");
    try {
      await deleteCalendarTask(taskEditor.id, mode);
      setTaskEditor(null);
      setRefreshKey((value) => value + 1);
    } catch (taskError) {
      setTaskEditorError(taskError?.message || "The task could not be deleted.");
    } finally {
      setSaving(false);
    }
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

  const importIcs = async (changeEvent) => {
    const file = changeEvent.target.files?.[0];
    changeEvent.target.value = "";
    if (!file) return;
    const calendar = workspace.calendars?.find((item) => item.is_default) || workspace.calendars?.[0];
    if (!calendar) return;
    try {
      const result = await importCalendarIcs({ calendarId: calendar.id, content: await file.text() });
      setError(`ICS import complete: ${result.imported} new, ${result.updated} updated, ${result.skipped} skipped.`);
      setRefreshKey((value) => value + 1);
    } catch (importError) {
      setError(importError?.message || "ICS file could not be imported.");
    }
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
    <div className="reservation-calendar-page calendar-workspace-page">
      <header className="reservation-calendar-toolbar">
        <div className="calendar-toolbar-copy"><span className="reservation-calendar-eyebrow">Workspace</span><h1>Calendar</h1><p>Bookings, events, tasks, reminders, and sync health in one place.</p></div>
        <div className="reservation-calendar-toolbar-actions">
          <button type="button" className="calendar-toolbar-action is-icon-only" onClick={() => setRefreshKey((value) => value + 1)} aria-label="Refresh calendar" title="Refresh calendar"><RefreshCw size={17} /></button>
          <label className={`calendar-toolbar-action calendar-import${calendarFeaturesAvailable ? "" : " is-disabled"}`} aria-disabled={!calendarFeaturesAvailable}><Plus size={16} /><span>Import</span><input type="file" accept=".ics,text/calendar" onChange={importIcs} disabled={!calendarFeaturesAvailable} /></label>
          <a className={`calendar-toolbar-action${calendarFeaturesAvailable ? "" : " is-disabled"}`} aria-disabled={!calendarFeaturesAvailable} onClick={(event) => { if (!calendarFeaturesAvailable) event.preventDefault(); }} href={getCalendarExportUrl({ start: rangeStart.toISOString(), end: rangeEnd.toISOString() })}><Download size={16} /><span>Export</span></a>
          <button type="button" className="calendar-toolbar-action is-primary" onClick={() => openNewEvent()} disabled={!calendarFeaturesAvailable}><Plus size={17} /><span>New event</span></button>
        </div>
      </header>

      <section className="calendar-summary-grid" aria-label="Calendar summary">
        <article><span>Calendars</span><strong>{(workspace.calendars?.length || 0) + 1}</strong></article>
        <article><span>Events in view</span><strong>{workspace.events?.length || 0}</strong></article>
        <article><span>Open tasks</span><strong>{openTasks.length}</strong></article>
        <article><span>Connections</span><strong>{workspace.connections?.length || 0}</strong></article>
      </section>

      <div className="calendar-control-bar">
        <button type="button" onClick={() => setFocusDate(new Date())}>Today</button>
        <button type="button" onClick={() => movePeriod(-1)} aria-label="Previous"><ChevronLeft size={18} /></button>
        <button type="button" onClick={() => movePeriod(1)} aria-label="Next"><ChevronRight size={18} /></button>
        <strong>{formatRange(rangeStart, rangeEnd)}</strong>
        <span className="calendar-control-spacer" />
        <div className="reservation-calendar-view-switch">{VIEWS.map((item) => <button type="button" className={view === item ? "is-active" : ""} key={item} onClick={() => setView(item)} onPointerEnter={item === "agenda" ? warmAgendaCache : undefined} onFocus={item === "agenda" ? warmAgendaCache : undefined}>{item}</button>)}</div>
      </div>

      {error && <div className="calendar-workspace-notice"><AlertTriangle size={17} />{error}<button type="button" onClick={() => setError("")}><X size={15} /></button></div>}

      <div className="reservation-calendar-layout">
        <aside className="reservation-calendar-sidebar calendar-workspace-sidebar">
          <div className="calendar-sidebar-category"><span>My calendars</span></div>
          <section className="calendar-sidebar-group calendar-calendars-panel">
            <SidebarSectionHeading section="calendars" icon={<CalendarDays size={16} />} title="Calendars" subtitle="Choose what appears" count={(workspace.calendars?.length || 0) + 1} expanded={expandedSidebarSections.has("calendars")} onToggle={toggleSidebarSection} />
            {expandedSidebarSections.has("calendars") && <div id="calendar-sidebar-calendars" className="calendar-sidebar-card calendar-source-list">{[...(workspace.calendars || []), { id: "reservations", name: "Reservations", color: "#f26b4a" }].map((calendar) => <label className="calendar-source-toggle" key={calendar.id}><input type="checkbox" checked={enabledCalendars.has(calendar.id)} onChange={() => toggleCalendar(calendar.id)} /><i style={{ background: calendar.color }} /><span>{calendar.name}</span>{calendar.is_default && <small>Default</small>}</label>)}</div>}
          </section>

          <div className="calendar-sidebar-category"><span>Planning</span></div>
          <section className="calendar-sidebar-group calendar-task-panel">
            <SidebarSectionHeading section="tasks" icon={<ListTodo size={16} />} title="Tasks" subtitle="Scheduled and unscheduled work" count={openTasks.length} expanded={expandedSidebarSections.has("tasks")} onToggle={toggleSidebarSection} />
            {expandedSidebarSections.has("tasks") && <div id="calendar-sidebar-tasks" className="calendar-sidebar-section-content"><form onSubmit={addTask}><div className="calendar-task-quick-fields"><input value={taskTitle} onChange={(event) => setTaskTitle(event.target.value)} placeholder="Add a task" aria-label="Task title" disabled={!calendarFeaturesAvailable} /><label><span>Schedule (optional)</span><input type="datetime-local" value={taskSchedule} onChange={(event) => setTaskSchedule(event.target.value)} aria-label="Task schedule" disabled={!calendarFeaturesAvailable} /></label></div><button type="submit" aria-label="Add task" disabled={!calendarFeaturesAvailable}><Plus size={16} /></button></form>{openTasks.slice(0, 6).map((task) => <button type="button" className="calendar-task" key={task.id} onClick={() => openTask(task)}><i className={`priority-${task.priority}`} /><span>{task.title}</span><small>{taskPlacementStart(task) ? new Date(taskPlacementStart(task)).toLocaleDateString() : "Unscheduled"}</small></button>)}</div>}
          </section>
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
        </aside>

        <main className="reservation-calendar-surface calendar-workspace-surface">
          {loading && <div className="reservation-calendar-loading">Loading calendar…</div>}
          {!loading && (view === "day" || view === "week") && <div className={`calendar-time-grid is-${view}`}><div className="calendar-grid-header"><span>{workspace.viewer_timezone || "Local time"}</span>{days.map((day) => <button type="button" key={dateKey(day)} className={sameDay(day, new Date()) ? "is-today" : ""} onClick={() => { setFocusDate(day); setView("day"); }}><small>{day.toLocaleDateString(undefined, { weekday: "short" })}</small><strong>{day.getDate()}</strong></button>)}</div><div className="calendar-grid-body"><div className="calendar-grid-hours">{HOURS.map((hour) => <span key={hour}>{new Date(2026, 0, 1, hour).toLocaleTimeString([], { hour: "numeric" })}</span>)}</div>{days.map((day) => <div className="calendar-grid-day" key={dateKey(day)}>{HOURS.map((hour) => { const slot = new Date(day); slot.setHours(hour, 0, 0, 0); return <button type="button" className="calendar-grid-slot" key={hour} aria-label={`Add to ${slot.toLocaleString([], { weekday: "long", month: "long", day: "numeric", hour: "numeric" })}`} onClick={() => openDateActions(slot, true)} />; })}{visibleCalendarItems.filter((entry) => sameDay(entry.startsAt, day)).map((entry) => { const { item } = entry; const start = new Date(entry.startsAt); const end = new Date(entry.endsAt); const top = (start.getHours() + start.getMinutes() / 60) * 48; const height = Math.max(34, Math.min(180, (end - start) / 3600000 * 48)); const calendar = calendarById.get(item.calendar_id); return <button type="button" key={entry.key} className={`calendar-grid-event is-${entry.kind === "task" ? "task" : item.source_type || "madar"}`} style={{ top, height, "--event-color": calendar?.color || "#f26b4a" }} onClick={() => entry.kind === "task" ? openTask(item) : openEvent(item)}><strong>{item.title}</strong><span>{formatTime(entry.startsAt)} · {entry.kind === "task" ? "Task" : calendar?.name || item.source_label}</span>{entry.kind === "task" ? <small>{item.status.replace("_", " ")}</small> : item.visibility && <small>{item.visibility.replace("calendar_default", "default privacy")}</small>}</button>; })}</div>)}</div></div>}
          {!loading && view === "month" && <div className="calendar-month-grid">{Array.from({ length: 42 }, (_, index) => addDays(rangeStart, index)).map((day) => { const dayItems = visibleCalendarItems.filter((entry) => sameDay(entry.startsAt, day)); return <section key={dateKey(day)} className={day.getMonth() !== focusDate.getMonth() ? "is-outside" : ""}><button type="button" aria-label={`Add to ${day.toLocaleDateString()}`} onClick={() => openDateActions(day)}>{day.getDate()}</button>{dayItems.slice(0, 4).map((entry) => <button type="button" className={`calendar-month-event${entry.kind === "task" ? " is-task" : ""}`} style={{ "--event-color": calendarById.get(entry.item.calendar_id)?.color || "#f26b4a" }} key={entry.key} onClick={() => entry.kind === "task" ? openTask(entry.item) : openEvent(entry.item)}><span>{formatTime(entry.startsAt)}</span>{entry.kind === "task" && <ListTodo size={12} aria-hidden="true" />}{entry.item.title}</button>)}{dayItems.length > 4 && <small>+{dayItems.length - 4} more</small>}</section>; })}</div>}
          {!loading && view === "agenda" && <div className="calendar-agenda">
            {unscheduledAgendaTasks.length > 0 && <><div className="calendar-agenda-section-title"><ListTodo size={15} /><strong>Unscheduled tasks</strong><span>{unscheduledAgendaTasks.length}</span></div>{unscheduledAgendaTasks.map((task) => <button type="button" className="calendar-agenda-task is-unscheduled" key={`task-${task.id}`} onClick={() => openTask(task)}><time><ListTodo size={19} /><span>Task</span></time><i /><div><strong>{task.title}</strong><span>{task.due_at ? `Due ${new Date(task.due_at).toLocaleString()}` : "Choose a time to place this task on your calendar"}</span></div><small>{task.status.replace("_", " ")}</small></button>)}</>}
            {agendaItems.length > 0 && <div className="calendar-agenda-section-title"><CalendarDays size={15} /><strong>Schedule</strong><span>{agendaItems.length}</span></div>}
            {agendaItems.map(({ kind, item }) => {
              if (kind === "task") return <button type="button" className="calendar-agenda-task" key={`task-${item.id}-${item.agenda_start}`} onClick={() => openTask(item)}><time><strong>{new Date(item.agenda_start).getDate()}</strong><span>{new Date(item.agenda_start).toLocaleDateString(undefined, { month: "short", weekday: "short" })}</span></time><i /><div><strong>{item.title}</strong><span><ListTodo size={14} /> {formatTime(item.agenda_start)}–{formatTime(item.agenda_end)} · Scheduled task{item.recurrence_rule ? ` · Repeats ${item.recurrence_rule.replace("FREQ=", "").toLowerCase()}` : ""}</span></div><small>{item.status.replace("_", " ")}</small></button>;
              const calendar = calendarById.get(item.calendar_id);
              return <button type="button" key={`event-${item.id}`} onClick={() => openEvent(item)}><time><strong>{new Date(item.starts_at).getDate()}</strong><span>{new Date(item.starts_at).toLocaleDateString(undefined, { month: "short", weekday: "short" })}</span></time><i style={{ background: calendar?.color || "#f26b4a" }} /><div><strong>{item.title}</strong><span><Clock3 size={14} /> {formatTime(item.starts_at)}–{formatTime(item.ends_at)} · {calendar?.name || item.source_label}</span></div><small>{item.read_only ? "Synced reservation" : item.visibility?.replace("calendar_default", "Default privacy")}</small></button>;
            })}
            {unscheduledAgendaTasks.length === 0 && agendaItems.length === 0 && <div className="reservation-calendar-empty"><CalendarDays size={30} /><strong>No events or tasks in this range</strong></div>}
          </div>}
        </main>
      </div>

      {editor && <EventEditor value={editor} calendars={workspace.calendars || []} saving={saving} conflict={conflict} onChange={(field, value) => setEditor((current) => ({ ...current, [field]: value }))} onClose={() => setEditor(null)} onSave={saveEvent} onDelete={removeEvent} />}
      {taskEditor && <TaskEditor value={taskEditor} connections={workspace.connections || []} saving={saving} error={taskEditorError} notice={taskEditorNotice} onChange={(field, value) => setTaskEditor((current) => ({ ...current, [field]: value }))} onClose={() => setTaskEditor(null)} onSave={saveTask} onDelete={removeTask} />}
      {dateAction && <DateActionChooser date={dateAction.date} onClose={() => setDateAction(null)} onTask={() => { const selection = dateAction; setDateAction(null); openNewTask(selection.date, selection.useSelectedTime); }} onReservation={() => { const selection = dateAction; setDateAction(null); openNewEvent(selection.date, selection.useSelectedTime); }} onOpenDay={() => { setFocusDate(dateAction.date); setView("day"); setDateAction(null); }} />}
      {editor?.id && history.length > 0 && <aside className="calendar-history-drawer"><header><History size={17} /><strong>Change history</strong></header>{history.slice(0, 8).map((item) => <div key={item.id}><strong>{item.action}</strong><span>{new Date(item.created_at).toLocaleString()} · {item.scope}</span></div>)}</aside>}
    </div>
  );
}
