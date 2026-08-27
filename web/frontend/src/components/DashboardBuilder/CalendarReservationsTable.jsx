import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, RefreshCw, Search } from "lucide-react";

import { listBuilderReservations } from "../PageBuilder/services/PageBuilder.api";

const STATUS_OPTIONS = ["new", "confirmed", "completed", "cancelled", "rejected"];
const present = (value) => value !== null && value !== undefined && value !== "";

function formatValue(value) {
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (value && typeof value === "object") return JSON.stringify(value);
  return present(value) ? String(value) : "—";
}

function formatDateTime(value, timezone) {
  if (!value) return "Not scheduled";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
      ...(timezone ? { timeZone: timezone } : {}),
    }).format(date);
  } catch {
    return date.toLocaleString();
  }
}

function reservationFormItems(reservation) {
  const snapshot = Array.isArray(reservation.field_snapshot)
    ? reservation.field_snapshot.find((item) => item?.reservation)
    : null;
  return Array.isArray(snapshot?.reservation?.formItems)
    ? snapshot.reservation.formItems
    : [];
}

function customAnswerRows(reservation) {
  const answers = reservation.payload?.customAnswers;
  if (!answers || typeof answers !== "object" || Array.isArray(answers)) return [];
  const labels = new Map(
    reservationFormItems(reservation)
      .filter((item) => item?.id)
      .map((item) => [String(item.id), item.label || "Custom question"])
  );
  return Object.entries(answers).map(([key, value]) => ({
    key,
    label: labels.get(String(key)) || "Custom answer",
    value,
  }));
}

export default function CalendarReservationsTable() {
  const [reservations, setReservations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const loadReservations = useCallback(async () => {
    const collected = [];
    let offset = 0;
    for (let page = 0; page < 100; page += 1) {
      const result = await listBuilderReservations({ limit: 100, offset });
      collected.push(...result.reservations);
      if (!result.pagination.has_more || result.reservations.length === 0) break;
      offset += result.reservations.length;
    }
    return collected;
  }, []);

  useEffect(() => {
    let active = true;
    loadReservations()
      .then((items) => active && setReservations(items))
      .catch((loadError) => active && setError(loadError?.message || "Reservations could not be loaded."))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [loadReservations, refreshKey]);

  const filteredReservations = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return reservations.filter((reservation) => {
      if (status && reservation.status !== status) return false;
      if (!normalizedQuery) return true;
      const searchable = [
        reservation.customer_name,
        reservation.customer_email,
        reservation.customer_phone,
        reservation.reservation_title,
        reservation.site_subdomain,
        reservation.status,
        reservation.id,
        ...customAnswerRows(reservation).flatMap((item) => [item.label, formatValue(item.value)]),
      ].filter(Boolean).join(" ").toLowerCase();
      return searchable.includes(normalizedQuery);
    });
  }, [query, reservations, status]);

  return (
    <section className="calendar-reservations-view" aria-labelledby="calendar-reservations-title">
      <header className="calendar-reservations-header">
        <div><span>Booking records</span><h2 id="calendar-reservations-title">Reservations</h2><p>Every reservation and all information submitted with it.</p></div>
        <strong>{filteredReservations.length} {filteredReservations.length === 1 ? "reservation" : "reservations"}</strong>
      </header>

      <div className="calendar-reservations-tools">
        <label className="calendar-reservations-search"><Search size={16} aria-hidden="true" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, email, phone, site, or answer" aria-label="Search reservations" /></label>
        <label><span>Status</span><select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter reservations by status"><option value="">All statuses</option>{STATUS_OPTIONS.map((item) => <option value={item} key={item}>{item[0].toUpperCase() + item.slice(1)}</option>)}</select></label>
        <button type="button" onClick={() => { setLoading(true); setError(""); setRefreshKey((value) => value + 1); }} disabled={loading}><RefreshCw size={16} aria-hidden="true" /><span>Refresh</span></button>
      </div>

      {error && <div className="calendar-reservations-error" role="alert"><AlertTriangle size={17} />{error}</div>}
      {loading && <div className="calendar-reservations-state">Loading reservations…</div>}
      {!loading && !error && filteredReservations.length === 0 && <div className="calendar-reservations-state"><strong>No reservations found</strong><span>{reservations.length ? "Try a different search or status." : "New bookings will appear here automatically."}</span></div>}

      {!loading && !error && filteredReservations.length > 0 && <div className="calendar-reservations-table-wrap">
        <table className="calendar-reservations-table">
          <thead><tr><th>Date and time</th><th>Customer</th><th>Contact</th><th>Reservation</th><th>Status</th><th>Submitted</th></tr></thead>
          <tbody>{filteredReservations.map((reservation) => (
            <tr key={reservation.id}>
              <td data-label="Date and time"><strong>{formatDateTime(reservation.starts_at, reservation.timezone)}</strong>{reservation.ends_at && <small>to {formatDateTime(reservation.ends_at, reservation.timezone)}</small>}</td>
              <td data-label="Customer"><strong>{reservation.customer_name || "Not provided"}</strong></td>
              <td data-label="Contact"><a href={reservation.customer_email ? `mailto:${reservation.customer_email}` : undefined}>{reservation.customer_email || "No email"}</a><small>{reservation.customer_phone || "No phone"}</small></td>
              <td data-label="Reservation"><strong>{reservation.reservation_title || "Reservation"}</strong><small>{reservation.site_subdomain || "Unknown site"}</small></td>
              <td data-label="Status"><span className={`calendar-reservation-status is-${reservation.status || "new"}`}>{reservation.status || "new"}</span></td>
              <td data-label="Submitted"><span>{formatDateTime(reservation.created_at)}</span></td>
            </tr>
          ))}</tbody>
        </table>
      </div>}
    </section>
  );
}
