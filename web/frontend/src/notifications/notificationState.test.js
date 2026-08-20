import { beforeEach, describe, expect, it } from "vitest";

import {
  notificationProviderConstants,
  readSessionDedup,
  rememberSessionDedup,
} from "./notificationState";

describe("notification session replay protection", () => {
  beforeEach(() => sessionStorage.clear());

  it("is identity-scoped and bounded", () => {
    const count = notificationProviderConstants.MAX_SESSION_DEDUP + 5;
    for (let index = 0; index < count; index += 1) {
      rememberSessionDedup("tenant-a:user-1", `tenant-a:user-1:${index}`);
    }

    const tenantA = readSessionDedup("tenant-a:user-1");
    expect(tenantA.size).toBe(notificationProviderConstants.MAX_SESSION_DEDUP);
    expect(tenantA.has("tenant-a:user-1:0")).toBe(false);
    expect(tenantA.has(`tenant-a:user-1:${count - 1}`)).toBe(true);
    expect(readSessionDedup("tenant-b:user-1").size).toBe(0);
  });
});
