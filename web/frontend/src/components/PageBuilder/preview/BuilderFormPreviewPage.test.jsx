import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import BuilderFormPreviewPage from "./BuilderFormPreviewPage";
import { fetchBuilderProject } from "../services/PageBuilder.api";

vi.mock("../services/PageBuilder.api", () => ({ fetchBuilderProject: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
it.each(["en", "ar"])("keeps duplicate choice selection independent in standalone %s preview", async languageMode => {
  const option = languageMode === "ar" ? "نعم" : "Same";
  fetchBuilderProject.mockResolvedValue({ draft_schema: { id: "p", pages: [], forms: [{ id: "f", title: "Choices", languageMode, defaultLanguage: languageMode,
    sections: [{ id: "s", title: "Choices", fields: [
      { id: "r", type: "radio", label: "Radio", options: [option, option] },
      { id: "c", type: "checkboxes", label: "Checkbox", options: [option, option] },
    ] }] }] } });
  render(<MemoryRouter initialEntries={["/preview/p/f"]}><Routes><Route path="/preview/:projectId/:formId" element={<BuilderFormPreviewPage />} /></Routes></MemoryRouter>);
  const radios = await screen.findAllByRole("radio");
  fireEvent.click(radios[1]);
  expect(radios.map(node => node.checked)).toEqual([false, true]);
  fireEvent.click(radios[0]);
  expect(radios.map(node => node.checked)).toEqual([true, false]);
  const boxes = screen.getAllByRole("checkbox");
  fireEvent.click(boxes[1]);
  expect(boxes.map(node => node.checked)).toEqual([false, true]);
  fireEvent.click(boxes[0]);
  expect(boxes.map(node => node.checked)).toEqual([true, true]);
  fireEvent.click(boxes[1]);
  expect(boxes.map(node => node.checked)).toEqual([true, false]);
  expect(document.querySelector("main").getAttribute("dir")).toBe(languageMode === "ar" ? "rtl" : "ltr");
});
