import { describe, expect, it } from "vitest";

import {
  getButtonColorPresentation,
  getButtonContrastRatio,
  getButtonContrastWarnings,
  normalizeButtonColor,
  normalizeButtonColorFields,
} from "./PageBuilder.buttonColors";

describe("button color model", () => {
  it("normalizes and preserves every explicit color", () => {
    const button = normalizeButtonColorFields({
      id: "button-1",
      type: "button",
      backgroundColor: "#1a2b3c",
      textColor: "#ffffff",
      hoverBackgroundColor: "#334455",
      hoverTextColor: "#abcdef",
      borderColor: "#000000",
    });
    expect(button).toMatchObject({
      backgroundColor: "#1A2B3C",
      textColor: "#FFFFFF",
      hoverBackgroundColor: "#334455",
      hoverTextColor: "#ABCDEF",
      borderColor: "#000000",
    });
  });

  it("rejects unsafe values and removes invalid values during normalization", () => {
    expect(normalizeButtonColor("url(javascript:alert(1))")).toBeNull();
    expect(normalizeButtonColor("#fff; color:red")).toBeNull();
    expect(normalizeButtonColor("#fff")).toBeNull();
    expect(normalizeButtonColorFields({ type: "button", backgroundColor: "red" }))
      .not.toHaveProperty("backgroundColor");
  });

  it("maps validated colors to narrowly scoped presentation variables", () => {
    const presentation = getButtonColorPresentation({
      type: "button",
      backgroundColor: "#112233",
      hoverTextColor: "#FFFFFF",
    });
    expect(presentation.className).toContain("has-button-background-color");
    expect(presentation.className).toContain("has-button-hover-text-color");
    expect(presentation.style).toEqual({
      "--button-background-color": "#112233",
      "--button-hover-text-color": "#FFFFFF",
    });
  });

  it("does not change buttons without explicit colors", () => {
    expect(getButtonColorPresentation({ type: "button" })).toEqual({ className: "", style: {} });
  });

  it("reports normal and hover contrast without blocking color choice", () => {
    expect(getButtonContrastRatio("#000000", "#FFFFFF")).toBeGreaterThan(7);
    expect(getButtonContrastWarnings({
      textColor: "#777777",
      backgroundColor: "#777777",
      hoverTextColor: "#888888",
      hoverBackgroundColor: "#888888",
    })).toHaveLength(2);
  });
});
