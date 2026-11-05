const modes = ["desktop", "tablet", "mobile"];
const object = value => value && typeof value === "object" && !Array.isArray(value) ? value : {};
const number = (value, min, max, fallback) => value === undefined || !Number.isFinite(Number(value))
  ? fallback : Math.round(Math.max(min, Math.min(max, Number(value))));

export function normalizeReservationLayout(value) {
  const source = object(value);
  return Object.fromEntries(modes.filter(mode => source[mode] && typeof source[mode] === "object" && !Array.isArray(source[mode]))
    .map(mode => {
      const entry = source[mode];
      return [mode, {
        columns: number(entry.columns, 1, 12, 12),
        ...(Number.isFinite(Number(entry.contentHeight)) && Number(entry.contentHeight) > 0
          ? { contentHeight: number(entry.contentHeight, 32, 2000, 40) } : {}),
        position: ["auto", "start", "center", "end", "custom"].includes(entry.position) ? entry.position : "auto",
        ...(entry.position === "custom" ? { startColumn: number(entry.startColumn, 1, 13 - number(entry.columns, 1, 12, 12), 1) } : {}),
        minHeight: number(entry.minHeight, 0, 1000, 0),
        spaceAbove: number(entry.spaceAbove, 0, 10000, 0),
        spaceBelow: number(entry.spaceBelow, 0, 160, 0),
      }];
    }));
}

export function getReservationLayout(item, mode = "desktop") {
  const layout = normalizeReservationLayout(item?.layout);
  return layout[mode] || (mode === "tablet" ? layout.desktop : null)
    || { columns: 12, position: "auto", minHeight: 0, spaceAbove: 0, spaceBelow: 0 };
}

export function getReservationLayoutStyle(item) {
  return Object.fromEntries(modes.flatMap(mode => {
    const entry = getReservationLayout(item, mode);
    const start = getReservationStartColumn(entry);
    return [[`--booking-${mode}-span`, entry.columns], [`--booking-${mode}-start`, start],
      [`--booking-${mode}-content-height`, entry.contentHeight ? `${entry.contentHeight}px` : "auto"]];
  }));
}

export function getReservationStartColumn(entry) {
  return entry.position === "custom" ? entry.startColumn : entry.position === "start" ? 1
    : entry.position === "center" ? Math.floor((12 - entry.columns) / 2) + 1
      : entry.position === "end" ? 13 - entry.columns : "auto";
}
