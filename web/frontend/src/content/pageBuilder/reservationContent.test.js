import { describe, expect, it } from "vitest";
import { getReservationContent } from "./reservationContent";

describe("built-in reservation translations", () => {
  it("translates every built-in message while preserving field identifiers", () => {
    const en = getReservationContent("en");
    const ar = getReservationContent("ar-PS");
    expect(ar.defaultFields).toEqual(en.defaultFields);
    expect(ar.requiredFields).toEqual(en.requiredFields);
    const visit = (english, arabic) => {
      expect(Object.keys(arabic).sort()).toEqual(Object.keys(english).sort());
      for (const [key, value] of Object.entries(english)) {
        if (["defaultFields", "requiredFields"].includes(key)) continue;
        if (typeof value === "object") visit(value, arabic[key]);
        else { expect(arabic[key]).toBeTruthy(); expect(arabic[key]).not.toBe(value); }
      }
    };
    visit(en, ar);
    expect(getReservationContent("fr")).toBe(en);
  });
});
