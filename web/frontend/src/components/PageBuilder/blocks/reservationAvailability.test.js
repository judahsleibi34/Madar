import { describe, expect, it } from "vitest";
import { getReservationSession, getWeeklySlotTimes, summarizeReservationSchedule } from "./reservationAvailability";

const times = { "2026-08-07": ["09:00"], "2026-08-21": ["14:00"], "2026-08-28": [] };
describe("weekly availability", () => {
  it("repeats on the source weekday without an expiry", () => {
    expect(getWeeklySlotTimes("2028-08-04", times, ["2026-08-07"])).toEqual(["09:00"]);
    expect(getWeeklySlotTimes("2026-08-08", times, ["2026-08-07"])).toEqual([]);
    expect(getWeeklySlotTimes("2026-07-31", times, ["2026-08-07"])).toEqual([]);
  });
  it("respects explicit overrides, including an empty day", () => {
    expect(getWeeklySlotTimes("2026-08-21", times, ["2026-08-07"])).toEqual(["14:00"]);
    expect(getWeeklySlotTimes("2026-08-28", times, ["2026-08-07"])).toEqual([]);
  });
  it("uses the latest enabled source for the weekday and stops when disabled", () => {
    expect(getWeeklySlotTimes("2026-09-04", times, ["2026-08-07", "2026-08-21"])).toEqual(["14:00"]);
    expect(getWeeklySlotTimes("2026-09-04", times, [])).toEqual([]);
    expect(getWeeklySlotTimes("2026-08-07", times, [])).toEqual(["09:00"]);
  });
  it("ignores malformed dates and missing sources", () => {
    expect(getWeeklySlotTimes("2026-02-30", times, ["2026-08-07"])).toEqual([]);
    expect(getWeeklySlotTimes("2026-09-04", times, ["bad", "2026-07-31"])).toEqual([]);
  });
});

describe("individual session settings", () => {
  const reservation = { timeSlotsByDate: { "2026-08-07": ["09:00", "11:00"], "2026-08-21": ["09:00"] },
    weeklyRepeatDates: ["2026-08-07"], sessionSettingsByDate: { "2026-08-07": { "11:00": { sessionType: "group", seatCapacity: 6 } } } };
  it("keeps private/group appointments on one day independent", () => {
    expect(getReservationSession(reservation, "2026-08-07", "09:00")).toEqual({ sessionType: "private", seatCapacity: 1 });
    expect(getReservationSession(reservation, "2026-08-07", "11:00")).toEqual({ sessionType: "group", seatCapacity: 6 });
  });
  it("inherits the exact weekly source but respects an explicit date", () => {
    expect(getReservationSession(reservation, "2026-08-14", "11:00")).toEqual({ sessionType: "group", seatCapacity: 6 });
    expect(getReservationSession(reservation, "2026-08-21", "11:00")).toEqual({ sessionType: "private", seatCapacity: 1 });
  });
});

describe("saved schedule summary", () => {
  it("separates saved appointments, mixed people limits and weekly repetition", () => {
    const map = { "2026-08-07": ["09:00", "09:00", "11:00", "", "99:99"], "2026-08-08": ["14:00"] };
    expect(summarizeReservationSchedule({ weeklyRepeatDates: ["2026-08-07"],
      sessionSettingsByDate: { "2026-08-07": { "11:00": { sessionType: "group", seatCapacity: 6 } } } }, map))
      .toEqual({ dates: 2, appointments: 3, capacity: 8, weekly: true });
  });
  it("does not invent a capacity while an appointment limit is unfinished", () => {
    expect(summarizeReservationSchedule({ sessionType: "group", seatCapacity: "" }, { "2026-08-07": ["09:00"] }).capacity).toBeNull();
    expect(summarizeReservationSchedule({}, {})).toEqual({ dates: 0, appointments: 0, capacity: 0, weekly: false });
  });
});
