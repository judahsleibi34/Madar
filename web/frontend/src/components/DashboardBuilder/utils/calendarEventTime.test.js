import { describe, expect, it } from "vitest";
import { eventWallTime, eventTimeToInstant, eventTimeZones } from "./calendarEventTime";

describe("event time zones", () => {
  it("renders stored instants in the event zone instead of the browser zone", () => {
    expect(eventWallTime("2026-01-15T14:30:00Z", "America/New_York")).toBe("2026-01-15T09:30");
    expect(eventWallTime("2026-01-15T14:30:00Z", "UTC")).toBe("2026-01-15T14:30");
  });
  it("saves selected wall-clock times with the correct winter and summer offsets", () => {
    expect(eventTimeToInstant("2026-01-15T09:30", "America/New_York")).toBe("2026-01-15T14:30:00.000Z");
    expect(eventTimeToInstant("2026-07-15T09:30", "America/New_York")).toBe("2026-07-15T13:30:00.000Z");
    expect(eventTimeToInstant("2026-07-15T09:30", "UTC")).toBe("2026-07-15T09:30:00.000Z");
  });
  it("handles non-hour offsets and date boundaries", () => {
    expect(eventTimeToInstant("2026-01-15T00:15", "Asia/Kolkata")).toBe("2026-01-14T18:45:00.000Z");
  });
  it("refuses nonexistent and ambiguous daylight-saving times", () => {
    expect(() => eventTimeToInstant("2026-03-08T02:30", "America/New_York")).toThrow(/skipped/);
    expect(() => eventTimeToInstant("2026-11-01T01:30", "America/New_York")).toThrow(/occurs twice/);
  });
  it("validates dates and preserves UTC/current zones in the selection list", () => {
    expect(() => eventTimeToInstant("2026-02-30T10:00", "UTC")).toThrow(/valid/);
    expect(() => eventTimeToInstant("", "UTC")).toThrow(/Choose a date/);
    expect(eventTimeZones("Asia/Hebron")).toContain("Asia/Hebron");
    expect(eventTimeZones("Asia/Hebron")).toContain("UTC");
  });
});
