import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createElementRenderer } from "./PageBuilder.elementRenderer";

afterEach(cleanup);

describe("mixed text blocks", () => {
  it("continues an H1 as normal text inside the same element", () => {
    const updateElementInlineText = vi.fn();
    const heading = {
      id: "heading-1",
      type: "heading",
      headingLevel: 1,
      content: "TitleBody",
      styles: {},
    };
    const renderElement = createElementRenderer({
      carouselElementTypes: new Set(),
      selected: { type: "element", id: heading.id },
      preview: false,
      getFreeElementStyle: () => ({}),
      getElementStyle: () => ({}),
      startDrag: vi.fn(),
      findElementLocation: vi.fn(),
      setInsertTarget: vi.fn(),
      setSelected: vi.fn(),
      captureCanvasTextSelection: vi.fn(),
      shouldIgnoreInlineTextBlur: () => false,
      updateElementInlineText,
      runElementAction: vi.fn(),
      renderConnectedForm: vi.fn(),
      getReservationBlockValue: vi.fn(),
    });

    render(renderElement(heading, false));
    const editable = screen.getByRole("textbox");
    const headingBlock = editable.querySelector("h1");
    const range = document.createRange();
    range.setStart(headingBlock.firstChild, 5);
    range.collapse(true);
    window.getSelection().removeAllRanges();
    window.getSelection().addRange(range);

    fireEvent.keyDown(editable, { key: "Enter" });

    expect(editable.tagName).toBe("DIV");
    expect(editable.querySelector("h1")?.textContent).toBe("Title");
    expect(editable.querySelector("p")?.textContent).toBe("Body");
    fireEvent.blur(editable);
    expect(updateElementInlineText).toHaveBeenCalledWith(
      heading.id,
      expect.objectContaining({
        content: "Title\nBody",
        textBlockFormats: ["h1", "text"],
      })
    );
  });
});
