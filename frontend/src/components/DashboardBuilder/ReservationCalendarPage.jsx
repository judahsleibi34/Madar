import { useEffect, useMemo, useState } from "react";
import {
  BellRing,
  CalendarDays,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Mail,
  MapPin,
  Search,
  User,
  X,
} from "lucide-react";

import { listBuilderReservations } from "../PageBuilder/services/PageBuilder.api";

const HOURS = Array.from({ length: 14 }, (_, index) => index + 7);
const STATUS_OPTIONS = [
  { id: "new", label: "New", color: "var(--theme-primary)" },
  { id: "confirmed", label: "Confirmed", color: "var(--theme-success)" },
  { id: "completed", label: "Completed", color: "var(--theme-info)" },
  { id: "cancelled", label: "Cancelled", color: "var(--theme-text-muted)" },
  { id: "rejected", label: "Rejected", color: "var(--theme-danger)" },
];

function startOfWeek(date) {
  const result = new Date(date);
  result.setHours(0, 0, 0, 0);
  result.setDate(result.getDate() - result.getDay());
  return result;
}

function addDays(date, amount) {
  const result = new Date(date);
  result.setDate(result.getDate() + amount);
  return result;
}

function sameDay(first, second) {
  return (
    first.getFullYear() === second.getFullYear() &&
    first.getMonth() === second.getMonth() &&
    first.getDate() === second.getDate()
  );
}

function dateKey(date) {
  return [
    date.getFullYear(),
    String(date.getMonth() + 1).padStart(2, "0"),
    String(date.getDate()).padStart(2, "0"),
  ].join("-");
}

function getEventDate(reservation) {
  const value = reservation?.starts_at || reservation?.payload?.starts_at;
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function eventTitle(reservation) {
  return (
    reservation?.reservation_title ||
    reservation?.payload?.service ||
    reservation?.customer_name ||
    "Reservation"
  );
}

function formatTime(date) {
  if (!date) return "Time not set";
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function formatHour(hour) {
  const date = new Date(2026, 0, 1, hour);
  return new Intl.DateTimeFormat(undefined, { hour: "numeric" }).format(date);
}

function formatWeekLabel(start) {
  const end = addDays(start, 6);
  const sameMonth =
    start.getMonth() === end.getMonth() &&
    start.getFullYear() === end.getFullYear();
  if (sameMonth) {
    return (
      new Intl.DateTimeFormat(undefined, { month: "long" }).format(start) +
      " " +
      start.getDate() +
      "–" +
      end.getDate() +
      ", " +
      end.getFullYear()
    );
  }
  return (
    new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(start) +
    " – " +
    new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    }).format(end)
  );
}

function buildMonthDays(date) {
  const first = new Date(date.getFullYear(), date.getMonth(), 1);
  const gridStart = startOfWeek(first);
  return Array.from({ length: 42 }, (_, index) => addDays(gridStart, index));
}

async function loadAllReservations() {
  const items = [];
  let offset = 0;

  for (let page = 0; page < 10; page += 1) {
    const result = await listBuilderReservations({ limit: 100, offset });
    items.push(...result.reservations);
    if (!result.pagination.has_more || result.reservations.length === 0) break;
    offset += result.reservations.length;
  }

  return items;
}

function MiniCalendar({ focusDate, onSelect }) {
  const days = useMemo(() => buildMonthDays(focusDate), [focusDate]);
  const today = new Date();

  return (
    <section className="reservation-calendar-mini" aria-label="Mini calendar">
      <strong>
        {new Intl.DateTimeFormat(undefined, {
          month: "long",
          year: "numeric",
        }).format(focusDate)}
      </strong>
      <div className="reservation-calendar-mini-weekdays" aria-hidden="true">
        {["S", "M", "T", "W", "T", "F", "S"].map((day, index) => (
          <span key={day + index}>{day}</span>
        ))}
      </div>
      <div className="reservation-calendar-mini-days">
        {days.map((day) => (
          <button
            type="button"
            key={dateKey(day)}
            className={[
              day.getMonth() !== focusDate.getMonth() ? "is-outside" : "",
              sameDay(day, focusDate) ? "is-selected" : "",
              sameDay(day, today) ? "is-today" : "",
            ].filter(Boolean).join(" ")}
            onClick={() => onSelect(day)}
            aria-label={day.toLocaleDateString()}
          >
            {day.getDate()}
          </button>
        ))}
      </div>
    </section>
  );
}

function ReservationDetail({ reservation, onClose }) {
  if (!reservation) return null;
  const start = getEventDate(reservation);
  const endValue = reservation?.ends_at ? new Date(reservation.ends_at) : null;
  const end = endValue && !Number.isNaN(endValue.getTime()) ? endValue : null;
  const status = String(reservation?.status || "new").toLowerCase();

  return (
    <aside className="reservation-calendar-detail" aria-label="Reservation details">
      <button
        type="button"
        className="reservation-calendar-detail-close"
        onClick={onClose}
        aria-label="Close reservation details"
      >
        <X size={18} />
      </button>
      <span className={"reservation-calendar-status reservation-calendar-status--" + status}>
        {status}
      </span>
      <h2>{eventTitle(reservation)}</h2>
      <div className="reservation-calendar-detail-list">
        <p>
          <CalendarDays size={17} />
          <span>
            {start
              ? new Intl.DateTimeFormat(undefined, {
                  weekday: "long",
                  month: "long",
                  day: "numeric",
                  year: "numeric",
                }).format(start)
              : "Date not set"}
          </span>
        </p>
        <p>
          <Clock3 size={17} />
          <span>
            {formatTime(start)}
            {end ? " – " + formatTime(end) : ""}
          </span>
        </p>
        <p>
          <User size={17} />
          <span>{reservation?.customer_name || "Guest name not provided"}</span>
        </p>
        {reservation?.customer_email && (
          <p>
            <Mail size={17} />
            <a href={"mailto:" + reservation.customer_email}>
              {reservation.customer_email}
            </a>
          </p>
        )}
        {reservation?.site_subdomain && (
          <p>
            <MapPin size={17} />
            <span>{reservation.site_subdomain}</span>
          </p>
        )}
      </div>
    </aside>
  );
}

export default function ReservationCalendarPage() {
  const [focusDate, setFocusDate] = useState(() => new Date());
  const [view, setView] = useState("week");
  const [reservations, setReservations] = useState([]);
  const [selectedStatuses, setSelectedStatuses] = useState(
    () => new Set(STATUS_OPTIONS.map((status) => status.id))
  );
  const [selectedReservation, setSelectedReservation] = useState(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    let active = true;
    loadAllReservations()
      .then((items) => {
        if (!active) return;
        setReservations(items);
        setLoadError("");
      })
      .catch(() => {
        if (!active) return;
        setLoadError("Reservations could not be loaded.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const visibleReservations = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return reservations.filter((reservation) => {
      const status = String(reservation?.status || "new").toLowerCase();
      if (!selectedStatuses.has(status)) return false;
      if (!normalizedQuery) return true;
      return [
        eventTitle(reservation),
        reservation?.customer_name,
        reservation?.customer_email,
        reservation?.site_subdomain,
      ].some((value) => String(value || "").toLowerCase().includes(normalizedQuery));
    });
  }, [query, reservations, selectedStatuses]);

  const weekStart = useMemo(() => startOfWeek(focusDate), [focusDate]);
  const weekDays = useMemo(
    () => Array.from({ length: 7 }, (_, index) => addDays(weekStart, index)),
    [weekStart]
  );
  const monthDays = useMemo(() => buildMonthDays(focusDate), [focusDate]);
  const today = new Date();
  const unscheduledCount = reservations.filter(
    (reservation) => !getEventDate(reservation)
  ).length;

  const reservationsByDay = useMemo(() => {
    const map = new Map();
    visibleReservations.forEach((reservation) => {
      const date = getEventDate(reservation);
      if (!date) return;
      const key = dateKey(date);
      const values = map.get(key) || [];
      values.push(reservation);
      map.set(key, values);
    });
    map.forEach((values) => {
      values.sort((first, second) => getEventDate(first) - getEventDate(second));
    });
    return map;
  }, [visibleReservations]);

  const movePeriod = (amount) => {
    const next = new Date(focusDate);
    if (view === "month") next.setMonth(next.getMonth() + amount);
    else next.setDate(next.getDate() + amount * 7);
    setFocusDate(next);
  };

  const toggleStatus = (status) => {
    setSelectedStatuses((current) => {
      const next = new Set(current);
      if (next.has(status)) next.delete(status);
      else next.add(status);
      return next;
    });
  };

  return (
    <div className="reservation-calendar-page">
      <header className="reservation-calendar-toolbar">
        <div>
          <span className="reservation-calendar-eyebrow">Workspace</span>
          <h1>Reservation calendar</h1>
          <p>See every booking and request in one schedule.</p>
        </div>
        <div className="reservation-calendar-toolbar-actions">
          <button type="button" className="reservation-calendar-today" onClick={() => setFocusDate(new Date())}>
            Today
          </button>
          <div className="reservation-calendar-period-controls">
            <button type="button" onClick={() => movePeriod(-1)} aria-label="Previous period">
              <ChevronLeft size={19} />
            </button>
            <button type="button" onClick={() => movePeriod(1)} aria-label="Next period">
              <ChevronRight size={19} />
            </button>
          </div>
          <strong className="reservation-calendar-period-label">
            {view === "week"
              ? formatWeekLabel(weekStart)
              : new Intl.DateTimeFormat(undefined, {
                  month: "long",
                  year: "numeric",
                }).format(focusDate)}
          </strong>
          <div className="reservation-calendar-view-switch" aria-label="Calendar view">
            <button
              type="button"
              className={view === "week" ? "is-active" : ""}
              onClick={() => setView("week")}
            >
              Week
            </button>
            <button
              type="button"
              className={view === "month" ? "is-active" : ""}
              onClick={() => setView("month")}
            >
              Month
            </button>
          </div>
        </div>
      </header>

      <div className="reservation-calendar-layout">
        <aside className="reservation-calendar-sidebar">
          <label className="reservation-calendar-search">
            <Search size={17} aria-hidden="true" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search reservations"
            />
          </label>

          <MiniCalendar focusDate={focusDate} onSelect={setFocusDate} />

          <section className="reservation-calendar-filters">
            <div className="reservation-calendar-section-title">
              <strong>Reservation status</strong>
              <span>{visibleReservations.length}</span>
            </div>
            {STATUS_OPTIONS.map((status) => {
              const enabled = selectedStatuses.has(status.id);
              return (
                <label key={status.id}>
                  <button
                    type="button"
                    className={enabled ? "is-enabled" : ""}
                    style={{ "--calendar-status-color": status.color }}
                    onClick={() => toggleStatus(status.id)}
                    aria-pressed={enabled}
                  >
                    {enabled && <Check size={13} />}
                  </button>
                  <span>{status.label}</span>
                  <small>
                    {
                      reservations.filter(
                        (reservation) =>
                          String(reservation?.status || "new").toLowerCase() === status.id
                      ).length
                    }
                  </small>
                </label>
              );
            })}
          </section>

          {unscheduledCount > 0 && (
            <div className="reservation-calendar-unscheduled">
              <BellRing size={18} />
              <div>
                <strong>{unscheduledCount} unscheduled</strong>
                <span>Requests without a selected time</span>
              </div>
            </div>
          )}
        </aside>

        <main className="reservation-calendar-surface">
          {loadError && <div className="reservation-calendar-error">{loadError}</div>}
          {loading && <div className="reservation-calendar-loading">Loading reservations…</div>}

          {!loading && view === "week" && (
            <div className="reservation-calendar-week">
              <div className="reservation-calendar-week-header">
                <div className="reservation-calendar-timezone">Local time</div>
                {weekDays.map((day) => (
                  <button
                    type="button"
                    key={dateKey(day)}
                    className={sameDay(day, today) ? "is-today" : ""}
                    onClick={() => setFocusDate(day)}
                  >
                    <span>
                      {new Intl.DateTimeFormat(undefined, { weekday: "short" }).format(day)}
                    </span>
                    <strong>{day.getDate()}</strong>
                  </button>
                ))}
              </div>

              <div className="reservation-calendar-week-body">
                <div className="reservation-calendar-hours">
                  {HOURS.map((hour) => (
                    <span key={hour}>{formatHour(hour)}</span>
                  ))}
                </div>
                {weekDays.map((day) => (
                  <div className="reservation-calendar-day-column" key={dateKey(day)}>
                    {HOURS.map((hour) => (
                      <div className="reservation-calendar-hour-line" key={hour} />
                    ))}
                    {(reservationsByDay.get(dateKey(day)) || []).map((reservation) => {
                      const start = getEventDate(reservation);
                      const rawEnd = reservation?.ends_at
                        ? new Date(reservation.ends_at)
                        : new Date(start.getTime() + 60 * 60 * 1000);
                      const end = Number.isNaN(rawEnd.getTime())
                        ? new Date(start.getTime() + 60 * 60 * 1000)
                        : rawEnd;
                      const startOffset =
                        (start.getHours() + start.getMinutes() / 60 - HOURS[0]) * 64;
                      const duration = Math.max(
                        0.55,
                        (end.getTime() - start.getTime()) / (60 * 60 * 1000)
                      );
                      const top = Math.max(2, Math.min(HOURS.length * 64 - 38, startOffset));
                      const height = Math.max(38, Math.min(duration * 64, 160));
                      const status = String(reservation?.status || "new").toLowerCase();

                      return (
                        <button
                          type="button"
                          className={"reservation-calendar-event reservation-calendar-event--" + status}
                          style={{ top: top + "px", height: height + "px" }}
                          key={reservation.id}
                          onClick={() => setSelectedReservation(reservation)}
                          title={eventTitle(reservation)}
                        >
                          <strong>{eventTitle(reservation)}</strong>
                          <span>{formatTime(start)}</span>
                          {height > 58 && (
                            <small>{reservation?.customer_name || "Guest"}</small>
                          )}
                        </button>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          )}

          {!loading && view === "month" && (
            <div className="reservation-calendar-month">
              <div className="reservation-calendar-month-weekdays">
                {["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"].map(
                  (day) => <span key={day}>{day}</span>
                )}
              </div>
              <div className="reservation-calendar-month-grid">
                {monthDays.map((day) => {
                  const dayReservations = reservationsByDay.get(dateKey(day)) || [];
                  return (
                    <section
                      className={[
                        day.getMonth() !== focusDate.getMonth() ? "is-outside" : "",
                        sameDay(day, today) ? "is-today" : "",
                      ].filter(Boolean).join(" ")}
                      key={dateKey(day)}
                    >
                      <button type="button" onClick={() => setFocusDate(day)}>
                        {day.getDate()}
                      </button>
                      <div>
                        {dayReservations.slice(0, 3).map((reservation) => (
                          <button
                            type="button"
                            className={
                              "reservation-calendar-month-event reservation-calendar-month-event--" +
                              String(reservation?.status || "new").toLowerCase()
                            }
                            key={reservation.id}
                            onClick={() => setSelectedReservation(reservation)}
                          >
                            <span>{formatTime(getEventDate(reservation))}</span>
                            {eventTitle(reservation)}
                          </button>
                        ))}
                        {dayReservations.length > 3 && (
                          <small>+{dayReservations.length - 3} more</small>
                        )}
                      </div>
                    </section>
                  );
                })}
              </div>
            </div>
          )}

          {!loading && visibleReservations.length === 0 && (
            <div className="reservation-calendar-empty">
              <CalendarDays size={30} />
              <strong>No reservations in this view</strong>
              <span>New bookings will appear here automatically.</span>
            </div>
          )}
        </main>
      </div>

      <ReservationDetail
        reservation={selectedReservation}
        onClose={() => setSelectedReservation(null)}
      />
    </div>
  );
}
