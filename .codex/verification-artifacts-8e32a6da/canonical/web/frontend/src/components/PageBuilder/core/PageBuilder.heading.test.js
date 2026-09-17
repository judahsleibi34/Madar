import { describe, expect, it } from "vitest";

import { getElementHeadingTag, getHeadingLevelFromFormat } from "./PageBuilder.heading";

describe("page builder heading levels", () => {
  it("keeps legacy headings as H1", () => {
    expect(getElementHeadingTag({ type: "heading" })).toBe("h1");
  });

  it.each([
    ["h1", 1],
    ["h2", 2],
    ["h3", 3],
  ])("maps %s to a persisted numeric level", (format, level) => {
    expect(getHeadingLevelFromFormat(format)).toBe(level);
    expect(getElementHeadingTag({ type: "heading", headingLevel: level })).toBe(format);
  });
});
