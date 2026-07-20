import { cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createElementRenderer } from "./PageBuilder.elementRenderer";

afterEach(cleanup);

const createRenderer = (updateElementInlineText = vi.fn()) => createElementRenderer({
  carouselElementTypes: new Set(),
  selected: { type: "element", id: "text-1" },
  preview: false,
  getFreeElementStyle: () => ({}),
  getElementStyle: () => ({}),
  startDrag: vi.fn(),
  findElementLocation: () => ({ isFree: true, sectionId: "section-1" }),
  setInsertTarget: vi.fn(),
  setSelected: vi.fn(),
  captureCanvasTextSelection: vi.fn(),
  shouldIgnoreInlineTextBlur: () => true,
  updateElementInlineText,
  runElementAction: vi.fn(),
  renderConnectedForm: vi.fn(),
  getReservationBlockValue: vi.fn(),
});

describe("Page Builder text element rendering", () => {
  it("applies a selected-word effect without duplicating editable text", () => {
    const content = "Design pages, collect responses, manage roles, and prototype workflows.";
    const renderElement = createRenderer();
    const element = {
      id: "text-1",
      type: "text",
      content,
      styles: { fontSize: "32px" },
      richTextStyles: [],
    };
    const view = render(renderElement(element, true));

    view.rerender(renderElement({
      ...element,
      richTextStyles: [{
        field: "content",
        start: 7,
        end: 12,
        fontStyle: "italic",
      }],
    }, true));

    expect(view.getByRole("textbox").textContent).toBe(content);
    expect(view.container.querySelector("span").textContent).toBe("pages");
  });
  it("never saves formatting-only DOM mutations as text edits", () => {
    const updateElementInlineText = vi.fn();
    const renderElement = createRenderer(updateElementInlineText);
    const view = render(renderElement({
      id: "text-1",
      type: "text",
      content: "Original server text",
      styles: { fontSize: "24px" },
    }, true));
    const textbox = view.getByRole("textbox");

    fireEvent.focus(textbox);
    textbox.append(" accidental render copy");
    fireEvent.blur(textbox);

    expect(updateElementInlineText).not.toHaveBeenCalled();
  });

  it("still saves genuine text input before the formatting toolbar takes focus", () => {
    const updateElementInlineText = vi.fn();
    const renderElement = createRenderer(updateElementInlineText);
    const view = render(renderElement({
      id: "text-1",
      type: "text",
      content: "Original text",
      styles: { fontSize: "24px" },
    }, true));
    const textbox = view.getByRole("textbox");

    fireEvent.focus(textbox);
    textbox.textContent = "Edited text";
    fireEvent.input(textbox);
    fireEvent.blur(textbox);

    expect(updateElementInlineText).toHaveBeenCalledWith(
      "text-1",
      expect.objectContaining({ content: "Edited text" })
    );
  });});
