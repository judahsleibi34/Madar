import { CalendarDays } from "lucide-react";
import { useEffect, useMemo } from "react";
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
  const fullDateFormatter = new Intl.DateTimeFormat(lang, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

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
          <label className="fixed-slot-date-control">
            <span>Appointment date</span>
            <div>
              <select
                aria-label="Appointment date"
                value={activeDate}
                disabled={disabled}
                onChange={(event) => onSelect?.(event.target.value, "")}
              >
                {fixedDates.map((dateValue) => {
                  const date = parseLocalDate(dateValue);
                  return date ? (
                    <option value={dateValue} key={dateValue}>{fullDateFormatter.format(date)}</option>
                  ) : null;
                })}
              </select>
              <CalendarDays size={17} aria-hidden="true" />
            </div>
          </label>

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
