import { describe, expect, it } from "vitest";
import { getAnswerValue, isOptionAnswerChecked, isCheckboxOptionChecked } from "./formAnswers";

describe("historical form answer representation", () => {
  it.each([null, undefined, false, true, 0, 1, "", "One"])("preserves primitive %s", value => {
    expect(getAnswerValue(value)).toBe(value);
  });
  it("unwraps once, including inherited values, without mutating inputs", () => {
    const inner = Object.freeze({ value: "nested" });
    const wrapped = Object.freeze({ value: inner, optionIndex: 1 });
    const array = Object.freeze([wrapped]);
    const plain = Object.freeze({ optionIndex: 1 });
    expect(getAnswerValue(wrapped)).toBe(inner);
    expect(getAnswerValue(array)).toBe(array);
    expect(getAnswerValue(plain)).toBe(plain);
    expect(getAnswerValue(Object.create({ value: "inherited" }))).toBe("inherited");
    expect(getAnswerValue({ value: undefined })).toBeUndefined();
  });
  it.each([
    ["same", "same", 1, true], [1, "1", 0, false], [null, null, 0, true],
    [{ value: "same", optionIndex: 1 }, "same", 0, false],
    [{ value: "different", optionIndex: 1 }, "same", 1, true],
    [{ optionIndex: "1" }, "same", 1, false],
    [{ optionIndex: 1 }, "same", "1", false],
    [{}, "same", undefined, true],
  ])("retains strict choice matching %#", (answer, option, index, expected) => {
    expect(isOptionAnswerChecked(answer, option, index)).toBe(expected);
    expect(isCheckboxOptionChecked(Object.freeze([answer]), option, index)).toBe(expected);
  });
  it("distinguishes duplicate labels by index but preserves scalar matching", () => {
    expect([0, 1].map(index => isOptionAnswerChecked({ value: "Same", optionIndex: 1 }, "Same", index))).toEqual([false, true]);
    expect([0, 1].map(index => isOptionAnswerChecked("Same", "Same", index))).toEqual([true, true]);
    expect(isCheckboxOptionChecked([], "Same", 0)).toBe(false);
    expect(isCheckboxOptionChecked(["Other", { value: "Same", optionIndex: 1 }], "Same", 1)).toBe(true);
  });
  it.each([null, undefined, {}, "Same", 1])("retains malformed checkbox errors: %s", answers => {
    expect(() => isCheckboxOptionChecked(answers, "Same", 0)).toThrow(TypeError);
  });
  it("does not swallow an existing value getter error", () => {
    const answer = { get value() { throw new Error("unreadable"); } };
    expect(() => getAnswerValue(answer)).toThrow("unreadable");
  });
});
