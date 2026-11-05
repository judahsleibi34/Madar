import { describe, expect, it } from "vitest";
import { offsetReservationDate, repeatReservationTimes } from "./reservationRepeat";

const base = {
  startDate: "2026-08-01", endDate: "2026-08-15", weekdays: [6], times: ["09:00"],
  timeSlotsByDate: { "2026-08-01": ["09:00"], "2026-08-08": ["14:00"] },
};

describe("weekly reservation dates", () => {
  it("includes the end date, preserves existing slots, and never duplicates slots", () => {
    const result = repeatReservationTimes(base);
    expect(result.timeSlotsByDate).toEqual({
      "2026-08-01": ["09:00"], "2026-08-08": ["09:00", "14:00"], "2026-08-15": ["09:00"],
    });
    expect(result).toMatchObject({ dateCount: 2, slotCount: 2 });
    expect(base.timeSlotsByDate["2026-08-08"]).toEqual(["14:00"]);
    expect(repeatReservationTimes({ ...base, timeSlotsByDate: result.timeSlotsByDate }).slotCount).toBe(0);
  });
  it("generates multiple weekdays across leap day and calendar boundaries", () => {
    const result = repeatReservationTimes({ ...base, startDate: "2028-02-28", endDate: "2028-03-02", weekdays: [2, 4], timeSlotsByDate: {} });
    expect(result.availableDates).toEqual(["2028-02-29", "2028-03-02"]);
    expect(offsetReservationDate("2028-02-28", 1)).toBe("2028-02-29");
  });
  it.each([
    { endDate: "" }, { endDate: "2026-02-30" }, { endDate: "2026-07-31" },
    { endDate: "2030-08-01" }, { weekdays: [] }, { times: [] }, { times: ["25:00"] },
  ])("refuses invalid or unbounded requests: %j", (updates) => {
    expect(repeatReservationTimes({ ...base, ...updates }).error).toBeTruthy();
  });
});
