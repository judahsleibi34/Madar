import { describe, expect, it } from "vitest";

import { resolveNotificationAction } from "./notificationActions";

describe("notification action resolution", () => {
  it("uses a same-tenant allowlisted calendar action", () => {
    expect(resolveNotificationAction(
      { kind: "calendar_task", tenant_id: "7", object_id: "task-1", path: "/calendar" },
      { tenantId: 7 },
    )).toEqual({ kind: "calendar_task", path: "/calendar" });
  });

  it("falls back rather than trusting a payload tenant or external path", () => {
    expect(resolveNotificationAction(
      { kind: "calendar_task", tenant_id: "8", path: "/calendar" }, { tenantId: 7 },
    ).path).toBe("/notifications");
    expect(resolveNotificationAction(
      { kind: "reservation", path: "https://evil.example" }, { tenantId: 7 },
    ).path).toBe("/notifications");
  });
});
