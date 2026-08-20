import { describe, expect, it } from "vitest";

import {
  expandTaskOccurrences,
  taskIsOpen,
  taskPlacementStart,
} from "./calendarTaskSchedule";

describe("calendar task scheduling", () => {
  it("uses scheduled start first and due time as a dated fallback", () => {
    expect(taskPlacementStart({
      scheduled_start: "2026-07-23T09:00:00Z",
      due_at: "2026-07-24T09:00:00Z",
    })).toBe("2026-07-23T09:00:00Z");
    expect(taskPlacementStart({ due_at: "2026-07-24T09:00:00Z" })).toBe(
      "2026-07-24T09:00:00Z"
    );
    expect(taskPlacementStart({})).toBeNull();
  });

  it("counts only active task statuses as open", () => {
    expect(taskIsOpen({ status: "todo" })).toBe(true);
    expect(taskIsOpen({ status: "in_progress" })).toBe(true);
    expect(taskIsOpen({ status: "blocked" })).toBe(true);
    expect(taskIsOpen({ status: "done" })).toBe(false);
    expect(taskIsOpen({ status: "cancelled" })).toBe(false);
  });

  it("places scheduled and due-only tasks once in the requested range", () => {
    const occurrences = expandTaskOccurrences([
      {
        id: "scheduled",
        scheduled_start: "2026-07-23T09:00:00Z",
        scheduled_end: "2026-07-23T10:00:00Z",
      },
      {
        id: "due-only",
        due_at: "2026-07-24T12:00:00Z",
        estimate_minutes: 30,
      },
      { id: "unscheduled" },
      { id: "outside", scheduled_start: "2026-08-23T09:00:00Z" },
    ], new Date("2026-07-20T00:00:00Z"), new Date("2026-07-27T00:00:00Z"));

    expect(occurrences.map((task) => task.id)).toEqual(["scheduled", "due-only"]);
    expect(occurrences[1].agenda_end).toBe("2026-07-24T12:30:00.000Z");
  });

  it("expands recurring tasks without duplicating their stable occurrence times", () => {
    const occurrences = expandTaskOccurrences([{
      id: "repeat",
      scheduled_start: "2026-07-20T09:00:00Z",
      recurrence_rule: "FREQ=DAILY",
      estimate_minutes: 15,
    }], new Date("2026-07-22T00:00:00Z"), new Date("2026-07-25T00:00:00Z"));

    expect(occurrences.map((task) => task.agenda_start)).toEqual([
      "2026-07-22T09:00:00.000Z",
      "2026-07-23T09:00:00.000Z",
      "2026-07-24T09:00:00.000Z",
    ]);
  });
});
