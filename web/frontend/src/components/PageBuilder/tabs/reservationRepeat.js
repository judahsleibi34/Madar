const DAY = 86400000;

const parseDate = (value) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return null;
  const date = new Date(`${value}T12:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value ? date : null;
};

export const offsetReservationDate = (value, days) => {
  const date = parseDate(value);
  return date ? new Date(date.getTime() + days * DAY).toISOString().slice(0, 10) : "";
};

export const reservationWeekday = (value) => parseDate(value)?.getUTCDay() ?? 0;

// Materialize finite dates in the existing format; no runtime recurrence rule or job is required.
export const repeatReservationTimes = ({ startDate, endDate, weekdays, times, timeSlotsByDate }) => {
  const start = parseDate(startDate);
  const end = parseDate(endDate);
  if (!start || !end || end <= start) return { error: "Choose an end date after the selected date." };
  if (end - start > 366 * DAY) return { error: "Choose an end date within 366 days of the selected date." };
  if (!weekdays.length) return { error: "Choose at least one weekday." };
  if (!times.length || times.some(time => !/^([01]\d|2[0-3]):[0-5]\d$/.test(time))) {
    return { error: "Add valid times to the selected date before repeating them." };
  }
  const nextMap = Object.fromEntries(Object.entries(timeSlotsByDate).map(([date, slots]) => [date, [...slots]]));
  let dateCount = 0;
  let slotCount = 0;
  for (let day = start.getTime() + DAY; day <= end.getTime(); day += DAY) {
    const date = new Date(day);
    if (!weekdays.includes(date.getUTCDay())) continue;
    const value = date.toISOString().slice(0, 10);
    const existing = nextMap[value] || [];
    const merged = [...new Set([...existing, ...times])].sort();
    const added = merged.length - existing.length;
    if (added > 0) dateCount += 1;
    slotCount += added;
    nextMap[value] = merged;
  }
  return { timeSlotsByDate: nextMap, availableDates: Object.keys(nextMap).sort(), dateCount, slotCount };
};
