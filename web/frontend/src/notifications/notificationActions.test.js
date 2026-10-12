import { describe, expect, it } from "vitest";

import { resolveNotificationAction } from "./notificationActions";

describe("notification action resolution", () => {
  it("accepts precise learner destinations without weakening tenant or URL checks", () => {
    const id = "11111111-1111-4111-8111-111111111111";
    for (const path of [`/my-learning/courses/${id}/lessons/${id}`, `/my-learning/courses/${id}/assessments/${id}`, "/my-learning/withdrawals", "/my-learning/referrals", "/my-learning/affiliate", "/my-learning/affiliate/application", `/my-learning/exchange/${id}`, `/e-learning/forms/responses/${id}`]) {
      expect(resolveNotificationAction({ kind: "learning", path, tenant_id: "7" }, { tenantId: 7 }).path).toBe(path);
      expect(resolveNotificationAction({ kind: "learning", path, tenant_id: "8" }, { tenantId: 7 }).path).toBe("/notifications");
      expect(resolveNotificationAction({ kind: "learning", path: `${path}?tenant=8` }, { tenantId: 7 }).path).toBe("/notifications");
    }
  });
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
