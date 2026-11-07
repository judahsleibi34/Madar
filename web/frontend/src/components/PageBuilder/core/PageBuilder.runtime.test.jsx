import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { createRuntimeFormRenderers } from "./PageBuilder.runtime";

afterEach(cleanup);
const form = { id: "form", languageMode: "en" };
function input(type, answer, setAnswer, options = ["Same", "Same"], lang = "en") {
  const renderer = createRuntimeFormRenderers({ project: {}, lang, runtimeAnswers: { form: { choice: answer } }, runtimeErrors: {}, setAnswer,
    getFieldType: () => ({ input: type }) });
  return renderer.renderFieldInput({ ...form, languageMode: lang }, { id: "choice", type, label: "Choice", options }, false, lang);
}
describe("embedded form choice rendering", () => {
  it.each([["Same", [true, true]], [{ value: "Same", optionIndex: 1 }, [false, true]]])("preserves radio representation %#", (answer, checked) => {
    const setAnswer = vi.fn();
    render(input("radio", answer, setAnswer));
    expect(screen.getAllByRole("radio").map(node => node.checked)).toEqual(checked);
    fireEvent.click(screen.getAllByRole("radio")[0]);
    if (!checked[0]) expect(setAnswer).toHaveBeenCalledWith("form", "choice", { value: "Same", optionIndex: 0 });
  });
  it("preserves indexed checkbox additions and removals", () => {
    const setAnswer = vi.fn();
    const { rerender } = render(input("checkboxes", [{ value: "Same", optionIndex: 1 }], setAnswer));
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes.map(node => node.checked)).toEqual([false, true]);
    fireEvent.click(boxes[0]);
    expect(setAnswer).toHaveBeenLastCalledWith("form", "choice", [{ value: "Same", optionIndex: 1 }, { value: "Same", optionIndex: 0 }]);
    rerender(input("checkboxes", ["Same"], setAnswer));
    expect(screen.getAllByRole("checkbox").map(node => node.checked)).toEqual([true, true]);
    fireEvent.click(screen.getAllByRole("checkbox")[0]);
    expect(setAnswer).toHaveBeenLastCalledWith("form", "choice", []);
  });
  it("keeps Arabic option presentation and indexed selection", () => {
    render(input("radio", { value: "نعم", optionIndex: 1 }, vi.fn(), ["نعم", "نعم"], "ar"));
    expect(screen.getAllByRole("radio").map(node => node.checked)).toEqual([false, true]);
    expect(screen.getAllByRole("radio")[1].closest("label").getAttribute("dir")).toBe("rtl");
  });
});
