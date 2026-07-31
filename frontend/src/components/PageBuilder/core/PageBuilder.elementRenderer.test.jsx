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

describe("button color rendering", () => {
  const renderer = (preview = true) => createElementRenderer({
    carouselElementTypes: new Set(),
    selected: { type: "", id: "" },
    preview,
    getFreeElementStyle: () => ({}),
    getElementStyle: () => ({ fontSize: "14px" }),
    startDrag: vi.fn(),
    findElementLocation: vi.fn(),
    setInsertTarget: vi.fn(),
    setSelected: vi.fn(),
    captureCanvasTextSelection: vi.fn(),
    shouldIgnoreInlineTextBlur: () => false,
    updateElementInlineText: vi.fn(),
    runElementAction: vi.fn(),
    renderConnectedForm: vi.fn(),
    getReservationBlockValue: vi.fn(),
  });

  it("applies explicit colors in preview and preserves focus/disabled semantics", () => {
    render(renderer(true)({
      id: "button-1",
      type: "button",
      content: "Continue",
      styles: {},
      disabled: true,
      backgroundColor: "#112233",
      textColor: "#FFFFFF",
      hoverBackgroundColor: "#334455",
      hoverTextColor: "#EEEEEE",
      borderColor: "#556677",
    }));
    const button = screen.getByRole("button", { name: "Continue" });
    expect(button.disabled).toBe(true);
    expect(button.className).toContain("has-button-background-color");
    expect(button.className).toContain("has-button-hover-background-color");
    expect(button.style.getPropertyValue("--button-border-color")).toBe("#556677");
  });

  it("leaves legacy button presentation untouched", () => {
    render(renderer(true)({ id: "button-legacy", type: "button", content: "Legacy", styles: {} }));
    const button = screen.getByRole("button", { name: "Legacy" });
    expect(button.className).not.toContain("has-button-");
    expect(button.getAttribute("style")).toContain("font-size");
  });
});
