import { describe, expect, it, vi } from "vitest";

import { createFormIdempotencyKey } from "./formSubmission";

describe("form submission idempotency", () => {
  it("creates bounded client keys using browser randomness", () => {
    const randomUUID = vi.spyOn(crypto, "randomUUID").mockReturnValue("00000000-0000-4000-8000-000000000000");
    const key = createFormIdempotencyKey();
    expect(key).toBe("madar-form-00000000-0000-4000-8000-000000000000");
    expect(key.length).toBeLessThanOrEqual(128);
    randomUUID.mockRestore();
  });
});
