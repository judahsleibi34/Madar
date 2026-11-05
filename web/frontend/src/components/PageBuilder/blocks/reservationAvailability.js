const cleanList = (items) => [...new Set(
  (Array.isArray(items) ? items : [])
    .map((item) => String(item || "").trim())
    .filter(Boolean)
)];

export const normalizeTimeSlotsByDate = (availableDates, timeSlots, timeSlotsByDate) => {
  const dates = cleanList(availableDates).sort();
  const legacyTimes = cleanList(timeSlots);
  const hasDateMap = timeSlotsByDate && typeof timeSlotsByDate === "object" && !Array.isArray(timeSlotsByDate);

  return Object.fromEntries(dates.map((date) => [
    date,
    hasDateMap ? cleanList(timeSlotsByDate[date]) : legacyTimes,
  ]));
};

export const flattenTimeSlotsByDate = (timeSlotsByDate) => cleanList(
  Object.values(timeSlotsByDate && typeof timeSlotsByDate === "object" ? timeSlotsByDate : {}).flat()
);

export const countConfiguredSlots = (timeSlotsByDate) => Object.values(
  timeSlotsByDate && typeof timeSlotsByDate === "object" ? timeSlotsByDate : {}
).reduce((total, times) => total + cleanList(times).length, 0);

const parseSlotDate = value => {
  if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T12:00:00Z`);
  return Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === value ? date : null;
};

// Explicit dates (including empty exceptions) take precedence over weekly rules.
// The latest enabled source for a weekday supplies its current times.
export const getWeeklySlotTimes = (date, timesByDate, weeklyRepeatDates = []) => {
  const requested = parseSlotDate(date);
  if (!requested) return [];
  if (Object.hasOwn(timesByDate, date)) return cleanList(timesByDate[date]);
  const source = (Array.isArray(weeklyRepeatDates) ? weeklyRepeatDates : [])
    .filter(value => {
      const parsed = parseSlotDate(value);
      return parsed && value <= date && parsed.getUTCDay() === requested.getUTCDay()
        && Object.hasOwn(timesByDate, value);
    }).sort().at(-1);
  return source ? cleanList(timesByDate[source]) : [];
};

// Explicit appointments keep their own settings. Weekly appointments inherit
// settings from the same source date that supplies their times.
export const getReservationSession = (reservation, date, time) => {
  const timesByDate = reservation.timeSlotsByDate || {};
  let source = date;
  if (!Object.hasOwn(timesByDate, date)) {
    const target = parseSlotDate(date);
    source = (Array.isArray(reservation.weeklyRepeatDates) ? reservation.weeklyRepeatDates : [])
      .filter(value => {
        const parsed = parseSlotDate(value);
        return target && parsed && value <= date && parsed.getUTCDay() === target.getUTCDay()
          && Object.hasOwn(timesByDate, value);
      }).sort().at(-1) || date;
  }
  const configured = reservation.sessionSettingsByDate?.[source]?.[time] || reservation;
  return configured.sessionType === "group"
    ? { sessionType: "group", seatCapacity: configured.seatCapacity }
    : { sessionType: "private", seatCapacity: 1 };
};

export const summarizeReservationSchedule = (reservation, timesByDate) => {
  const dates = Object.keys(timesByDate).filter(date => parseSlotDate(date));
  let appointments = 0;
  let capacity = 0;
  let incomplete = false;
  for (const date of dates) {
    for (const time of cleanList(timesByDate[date])) {
      if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(time)) continue;
      appointments += 1;
      const session = getReservationSession({ ...reservation, timeSlotsByDate: timesByDate }, date, time);
      if (!Number.isInteger(session.seatCapacity) || session.seatCapacity < 1 || session.seatCapacity > 1000
        || (session.sessionType === "group" && session.seatCapacity < 2)) incomplete = true;
      else capacity += session.seatCapacity;
    }
  }
  const weekly = Array.isArray(reservation.weeklyRepeatDates) && reservation.weeklyRepeatDates.some(date =>
    dates.includes(date) && cleanList(timesByDate[date]).some(time => /^([01]\d|2[0-3]):[0-5]\d$/.test(time)));
  return { dates: dates.length, appointments, capacity: incomplete ? null : capacity, weekly };
};
