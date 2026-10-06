import { describe, expect, it } from "vitest";

import {
  MAX_BUILDER_TEXT_FONT_SIZE_PX,
  parseBuilderTextFontSize,
  getBuilderElementName,
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

it("uses plain English for technical element names and keeps custom names", () => {
  expect(getBuilderElementName({ name: "academyFeaturedCourses", type: "academyFeaturedCourses" })).toBe("Featured Courses");
  expect(getBuilderElementName({ type: "academyCourseCollection" })).toBe("Course Collection");
  expect(getBuilderElementName({ name: "Recommended for you", type: "academyFeaturedCourses" })).toBe("Recommended for you");
  expect(getBuilderElementName({ type: "imageButton" })).toBe("Image Button");
  expect(getBuilderElementName({ type: "customWidget" })).toBe("Custom Widget");
  expect(getBuilderElementName()).toBe("Element");
});
