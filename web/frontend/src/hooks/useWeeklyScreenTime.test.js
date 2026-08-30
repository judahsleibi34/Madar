import { describe, expect, it } from "vitest";
import {
  formatWeeklyScreenTime,
  getWeeklyScreenTimeWeekKey,
} from "./useWeeklyScreenTime";

describe("weekly screen time", () => {
  it("uses Monday as the start of the tracking week", () => {
    expect(getWeeklyScreenTimeWeekKey(new Date(2026, 7, 30, 12))).toBe("2026-08-24");
    expect(getWeeklyScreenTimeWeekKey(new Date(2026, 7, 31, 12))).toBe("2026-08-31");
  });

  it("formats active time for dashboard display", () => {
    expect(formatWeeklyScreenTime(0)).toBe("0 min");
    expect(formatWeeklyScreenTime(59 * 60)).toBe("59 min");
    expect(formatWeeklyScreenTime(60 * 60)).toBe("1h");
    expect(formatWeeklyScreenTime((2 * 60 + 14) * 60)).toBe("2h 14m");
  });
});