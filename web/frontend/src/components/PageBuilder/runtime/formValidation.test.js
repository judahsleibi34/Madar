import { describe, expect, it } from "vitest";

import { getRuntimeFieldError, getRuntimeFormErrors } from "./formValidation";

describe("runtime form validation", () => {
  it("flags forgotten required fields", () => {
    expect(getRuntimeFieldError({ id: "name", label: "Full name", required: true }, ""))
      .toBe("Full name is required.");
  });

  it("treats whitespace as a missing required answer", () => {
    expect(getRuntimeFieldError({ label: "Full name", required: true }, "   "))
      .toBe("Full name is required.");
  });

  it.each([
    ["email", "not-an-email", "Enter a valid email address."],
    ["url", "example", "Enter a valid website address."],
    ["phone", "call me", "Enter a valid phone number."],
    ["number", "twelve", "Enter a valid number."],
    ["date", "2026-02-31", "Choose a valid date."],
    ["time", "25:80", "Choose a valid time."],
  ])("flags invalid %s values", (type, value, message) => {
    expect(getRuntimeFieldError({ id: type, label: type, type }, value)).toBe(message);
  });

  it("accepts formatted money and rejects invalid amounts", () => {
    expect(getRuntimeFieldError({ type: "money" }, "7,500")).toBe("");
    expect(getRuntimeFieldError({ type: "money" }, "many")).toBe("Enter a valid amount.");
  });

  it("rejects choices that are not in the published options", () => {
    const field = { type: "dropdown", options: ["One", "Two"] };
    expect(getRuntimeFieldError(field, "Three")).toBe("Choose one of the available options.");
    expect(getRuntimeFieldError(field, "Two")).toBe("");
  });

  it("validates every checkbox choice and scale range", () => {
    expect(getRuntimeFieldError(
      { type: "checkboxes", options: ["One", "Two"] },
      [{ value: "One", optionIndex: 0 }, { value: "Unknown", optionIndex: 2 }]
    )).toBe("Choose only from the available options.");
    expect(getRuntimeFieldError({ type: "linearScale", scaleMin: 1, scaleMax: 5 }, 6))
      .toBe("Choose a value from 1 to 5.");
  });

  it("validates uploaded file metadata and size", () => {
    expect(getRuntimeFieldError({ type: "file", maxFileSizeMb: 1 }, { name: "large.pdf", size: 2_000_000 }))
      .toBe("Choose a file smaller than 1MB.");
  });

  it("returns every field error so all mistakes can be highlighted", () => {
    expect(getRuntimeFormErrors([
      { id: "email", label: "Email", type: "email", required: true },
      { id: "phone", label: "Phone", type: "phone" },
    ], { email: "bad", phone: "abc" })).toEqual({
      email: "Enter a valid email address.",
      phone: "Enter a valid phone number.",
    });
  });
});
