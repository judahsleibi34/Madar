function formatter(timeZone) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  });
}

function wallParts(format, instant) {
  const parts = Object.fromEntries(format.formatToParts(new Date(instant)).map(({ type, value }) => [type, value]));
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

export function eventWallTime(instant, timeZone) {
  return wallParts(formatter(timeZone), instant);
}

// Match the selected wall-clock time against actual offsets around that date.
// Gaps and repeated DST hours need an explicit user choice, never a silent shift.
export function eventTimeToInstant(value, timeZone) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) throw new Error("Choose a date and time for the event.");
  const nominal = Date.parse(`${value}:00Z`);
  if (!Number.isFinite(nominal) || new Date(nominal).toISOString().slice(0, 16) !== value) throw new Error("Choose a valid event date and time.");
  const format = formatter(timeZone);
  const offsets = new Set();
  for (let hours = -36; hours <= 36; hours += 6) {
    const sample = nominal + hours * 3600000;
    offsets.add(Date.parse(`${wallParts(format, sample)}:00Z`) - sample);
  }
  const matches = [...offsets].map((offset) => nominal - offset)
    .filter((instant) => wallParts(format, instant) === value);
  if (!matches.length) throw new Error("This time is skipped by a clock change in the selected time zone. Choose another time.");
  if (matches.length > 1) throw new Error("This time occurs twice during a clock change. Choose another time or use UTC to specify the exact time.");
  return new Date(matches[0]).toISOString();
}

export function eventTimeZones(current) {
  const local = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  const zones = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("timeZone") : ["Asia/Hebron", "Asia/Jerusalem", "Europe/London", "America/New_York"];
  return [...new Set([local, "UTC", current, ...zones].filter(Boolean))];
}
