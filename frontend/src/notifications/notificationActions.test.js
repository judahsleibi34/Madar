import { describe, expect, it } from "vitest";

import { getSafeNotificationActionPath } from "./notificationActions";

describe("notification action navigation", () => {
  it("accepts only the current canonical action paths", () => {
    expect(getSafeNotificationActionPath({ kind: "calendar_task", path: "/calendar" }))
      .toBe("/calendar");
    expect(getSafeNotificationActionPath({ kind: "form_submission", path: "/notifications" }))
      .toBe("/notifications");
  });

  it.each([
    "https://evil.example/steal",
    "//evil.example/steal",
    "javascript:alert(1)",
    "data:text/html,evil",
    "/\\evil.example",
    "/calendar?tenant=other",
  ])("falls back for unsafe path %s", (path) => {
    expect(getSafeNotificationActionPath({ kind: "calendar_task", path }))
      .toBe("/notifications");
  });

  it("does not let an action kind use another kind's route", () => {
    expect(getSafeNotificationActionPath({ kind: "reservation", path: "/calendar" }))
      .toBe("/notifications");
  });
});
