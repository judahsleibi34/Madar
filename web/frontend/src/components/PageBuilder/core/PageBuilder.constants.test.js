import { describe, expect, it } from "vitest";

import {
  MAX_BUILDER_TEXT_FONT_SIZE_PX,
  parseBuilderTextFontSize,
} from "./PageBuilder.constants";

describe("builder text font-size bounds", () => {
  it("accepts normal and maximum values", () => {
    expect(parseBuilderTextFontSize("72px")).toBe(72);
    expect(parseBuilderTextFontSize(String(MAX_BUILDER_TEXT_FONT_SIZE_PX))).toBe(256);
  });

  it("rejects values above the maximum and malformed values", () => {
    expect(parseBuilderTextFontSize("257px")).toBeNull();
    expect(parseBuilderTextFontSize("calc(100px + 1vw)")).toBeNull();
  });
});
