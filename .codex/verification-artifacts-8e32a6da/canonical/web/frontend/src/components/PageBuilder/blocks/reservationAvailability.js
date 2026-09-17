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