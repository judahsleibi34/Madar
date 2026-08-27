import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { normalizeTimeSlotsByDate } from "./reservationAvailability";

const normalizeOptions = (items) => [...new Set(
  (Array.isArray(items) ? items : [])
    .map((item) => String(item || "").trim())
    .filter(Boolean)
)];

const parseLocalDate = (dateValue) => {
  const [year, month, day] = String(dateValue).split("-").map(Number);
  if (!year || !month || !day) return null;
  return new Date(year, month - 1, day, 12);
};

const formatLocalDate = (date) => {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
};

const startOfMonth = (date) => new Date(date.getFullYear(), date.getMonth(), 1, 12);

const shiftMonth = (date, offset) => (
  new Date(date.getFullYear(), date.getMonth() + offset, 1, 12)
);

const formatSlotTime = (timeValue, lang) => {
  const [hours, minutes] = String(timeValue).split(":").map(Number);
  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return timeValue;
  return new Intl.DateTimeFormat(lang, {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(2000, 0, 1, hours, minutes));
};

export default function FixedSlotPicker({
  dates = [],
  times = [],
  timesByDate,
  selectedDate = "",
  selectedTime = "",
  disabled = false,
  error = "",
  lang = "en",
  direction = "ltr",
  onSelect,
}) {
  const fixedDates = useMemo(() => normalizeOptions(dates).sort(), [dates]);
  const availableDateSet = useMemo(() => new Set(fixedDates), [fixedDates]);
  const normalizedTimesByDate = useMemo(
    () => normalizeTimeSlotsByDate(fixedDates, times, timesByDate),
    [fixedDates, times, timesByDate]
  );
  const activeDate = fixedDates.includes(selectedDate) ? selectedDate : fixedDates[0] || "";
  const activeTimes = useMemo(
    () => normalizedTimesByDate[activeDate] || [],
    [activeDate, normalizedTimesByDate]
  );
  const activeDateValue = parseLocalDate(activeDate);
  const initialCalendarDate = activeDateValue || new Date();
  const [calendarMonth, setCalendarMonth] = useState(() => startOfMonth(initialCalendarDate));
  const fullDateFormatter = useMemo(() => new Intl.DateTimeFormat(lang, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  }), [lang]);
  const monthFormatter = useMemo(() => new Intl.DateTimeFormat(lang, {
    month: "long",
    year: "numeric",
  }), [lang]);
  const weekdayFormatter = useMemo(() => new Intl.DateTimeFormat(lang, {
    weekday: "short",
  }), [lang]);
  const weekdays = useMemo(() => Array.from({ length: 7 }, (_, index) => (
    weekdayFormatter.format(new Date(2026, 0, 4 + index, 12))
  )), [weekdayFormatter]);
  const calendarCells = useMemo(() => {
    const year = calendarMonth.getFullYear();
    const month = calendarMonth.getMonth();
    const firstWeekday = new Date(year, month, 1, 12).getDay();
    const daysInMonth = new Date(year, month + 1, 0, 12).getDate();
    return Array.from({ length: 42 }, (_, index) => {
      const day = index - firstWeekday + 1;
      return day > 0 && day <= daysInMonth ? new Date(year, month, day, 12) : null;
    });
  }, [calendarMonth]);

  useEffect(() => {
    if (!activeDateValue) return;
    setCalendarMonth(startOfMonth(activeDateValue));
  }, [activeDate]);

  useEffect(() => {
    if (selectedDate || fixedDates.length === 0) return;
    onSelect?.(fixedDates[0], "");
  }, [fixedDates, onSelect, selectedDate]);

  useEffect(() => {
    if (!selectedDate || !selectedTime || activeTimes.includes(selectedTime)) return;
    onSelect?.(activeDate, "");
  }, [activeDate, activeTimes, onSelect, selectedDate, selectedTime]);

  return (
    <fieldset className={`fixed-slot-picker ${error ? "has-error" : ""}`} dir={direction === "rtl" ? "rtl" : "ltr"}>
      <legend className="sr-only">Choose an appointment date and time</legend>

      {fixedDates.length > 0 ? (
        <div className="fixed-slot-booking-controls">
          <section className="fixed-slot-calendar" aria-label="Appointment date">
            <header>
              <button
                type="button"
                aria-label="Previous month"
                disabled={disabled}
                onClick={() => setCalendarMonth((current) => shiftMonth(current, -1))}
              >
                <ChevronLeft size={20} aria-hidden="true" />
              </button>
              <p aria-live="polite">{monthFormatter.format(calendarMonth)}</p>
              <button
                type="button"
                aria-label="Next month"
                disabled={disabled}
                onClick={() => setCalendarMonth((current) => shiftMonth(current, 1))}
              >
                <ChevronRight size={20} aria-hidden="true" />
              </button>
            </header>

            <div className="fixed-slot-calendar-weekdays" aria-hidden="true">
              {weekdays.map((weekday, index) => <span key={`${weekday}-${index}`}>{weekday}</span>)}
            </div>

            <div className="fixed-slot-calendar-days">
              {calendarCells.map((date, index) => {
                if (!date) return <span className="is-empty" aria-hidden="true" key={`empty-${index}`} />;
                const dateValue = formatLocalDate(date);
                const available = availableDateSet.has(dateValue);
                const selected = dateValue === activeDate;
                const dateLabel = fullDateFormatter.format(date);
                return (
                  <button
                    type="button"
                    className={`${available ? "is-available" : "is-unavailable"} ${selected ? "is-selected" : ""}`}
                    key={dateValue}
                    aria-label={`${dateLabel}${available ? ", available" : ", unavailable"}`}
                    aria-pressed={selected}
                    disabled={disabled || !available}
                    onClick={() => onSelect?.(dateValue, "")}
                  >
                    <span>{date.getDate()}</span>
                    {available && <i aria-hidden="true" />}
                  </button>
                );
              })}
            </div>
          </section>

          <div className="fixed-slot-times">
            <span>Available time slots</span>
            {activeTimes.length > 0 ? (
              <div>
                {activeTimes.map((timeValue) => {
                  const selected = activeDate === selectedDate && selectedTime === timeValue;
                  const timeLabel = formatSlotTime(timeValue, lang);
                  return (
                    <button
                      type="button"
                      key={`${activeDate}_${timeValue}`}
                      className={selected ? "is-selected" : ""}
                      aria-pressed={selected}
                      aria-label={`${activeDateValue ? fullDateFormatter.format(activeDateValue) : activeDate} at ${timeLabel}`}
                      disabled={disabled || !activeDate}
                      onClick={() => onSelect?.(activeDate, timeValue)}
                    >
                      {timeLabel}
                    </button>
                  );
                })}
              </div>
            ) : <div className="fixed-slot-empty">No times are available for this date.</div>}
          </div>
        </div>
      ) : (
        <div className="fixed-slot-empty">No appointment slots are available yet.</div>
      )}

      {error && <strong className="fixed-slot-error">{error}</strong>}
    </fieldset>
  );
}
