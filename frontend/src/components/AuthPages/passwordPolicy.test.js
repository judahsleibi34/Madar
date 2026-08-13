import { describe, expect, it } from "vitest";

import { PASSWORD_MIN_LENGTH, meetsMinimumPasswordPolicy } from "./passwordPolicy";

describe("shared password minimum", () => {
  it("uses the same eight-character minimum for account password forms", () => {
    expect(PASSWORD_MIN_LENGTH).toBe(8);
    expect(meetsMinimumPasswordPolicy("1234567")).toBe(false);
    expect(meetsMinimumPasswordPolicy("12345678")).toBe(true);
  });
});
