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
  selectedDate = "",
  selectedTime = "",
  disabled = false,
  error = "",
  lang = "en",
  onSelect,
}) {
  const fixedDates = normalizeOptions(dates).sort();
  const fixedTimes = normalizeOptions(times);
  const fullDateFormatter = new Intl.DateTimeFormat(lang, {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  const weekdayFormatter = new Intl.DateTimeFormat(lang, { weekday: "short" });
  const monthFormatter = new Intl.DateTimeFormat(lang, { month: "short" });

  return (
    <fieldset className={`fixed-slot-picker ${error ? "has-error" : ""}`}>
      <legend>Choose a date and time</legend>
      <p>Select one of the available appointment times.</p>

      {fixedDates.length > 0 && fixedTimes.length > 0 ? (
        <div className="fixed-slot-agenda">
          {fixedDates.map((dateValue) => {
            const date = parseLocalDate(dateValue);
            if (!date) return null;

            return (
              <div className="fixed-slot-row" key={dateValue}>
                <div className="fixed-slot-date">
                  <span>{weekdayFormatter.format(date)}</span>
                  <strong>{date.getDate()}</strong>
                  <small>{monthFormatter.format(date)}</small>
                </div>
                <div className="fixed-slot-times">
                  <span>Available times</span>
                  <div>
                    {fixedTimes.map((timeValue) => {
                      const selected = selectedDate === dateValue && selectedTime === timeValue;
                      const timeLabel = formatSlotTime(timeValue, lang);

                      return (
                        <button
                          type="button"
                          key={`${dateValue}_${timeValue}`}
                          className={selected ? "is-selected" : ""}
                          aria-pressed={selected}
                          aria-label={`${fullDateFormatter.format(date)} at ${timeLabel}`}
                          disabled={disabled}
                          onClick={() => onSelect?.(dateValue, timeValue)}
                        >
                          {timeLabel}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="fixed-slot-empty">No appointment slots are available yet.</div>
      )}

      {error && <strong className="fixed-slot-error">{error}</strong>}
    </fieldset>
  );
}