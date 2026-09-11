import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  collapseAccidentalTextDuplication,
  createDomTextRange,
  getFloatingToolbarPlacement,
  getSelectionMoveHandlePlacement,
  getEditableTextWithLineBreaks,
  getTextBlockFormats,
  getTextBlockIndexesForRange,
  getEditableSelectionBlockIndexes,
  replaceRichTextRangeStyle,
  renderRichText,
  renderRichTextBlocks,
  splitEditableLines,
} from "./PageBuilder.text";

describe("replaceRichTextRangeStyle", () => {
  it("preserves the surrounding normal-text size when a selected word is resized", () => {
    expect(replaceRichTextRangeStyle(
      [{ field: "content", itemIndex: null, start: 0, end: 20, fontSize: "17px" }],
      { field: "content", itemIndex: null, start: 6, end: 10 },
      "fontSize",
      "24px"
    )).toEqual([
      { field: "content", itemIndex: null, start: 0, end: 6, fontSize: "17px" },
      { field: "content", itemIndex: null, start: 10, end: 20, fontSize: "17px" },
      { field: "content", itemIndex: null, start: 6, end: 10, fontSize: "24px" },
    ]);
  });

  it("replaces bold without removing another style on the same range", () => {
    expect(replaceRichTextRangeStyle(
      [{ field: "content", start: 0, end: 12, fontWeight: "700", fontStyle: "italic" }],
      { field: "content", itemIndex: null, start: 3, end: 8 },
      "fontWeight",
      "400"
    )).toEqual([
      { field: "content", start: 0, end: 3, fontWeight: "700", fontStyle: "italic" },
      { field: "content", start: 3, end: 8, fontStyle: "italic" },
      { field: "content", start: 8, end: 12, fontWeight: "700", fontStyle: "italic" },
      { field: "content", itemIndex: null, start: 3, end: 8, fontWeight: "400" },
    ]);
  });
});

afterEach(cleanup);

describe("renderRichText", () => {
  it("counts an empty paragraph placeholder as one blank row", () => {
    const { container } = render(
      <div>
        <h2 data-builder-text-block="h2">Title</h2>
        <p data-builder-text-block="text"><br /></p>
        <p data-builder-text-block="text">Body</p>
      </div>
    );

    expect(getEditableTextWithLineBreaks(container.firstChild)).toBe("Title\n\nBody");
  });

  it("preserves Chrome-style pasted block boundaries without internal markers", () => {
    const { container } = render(
      <div contentEditable suppressContentEditableWarning>
        <div>First pasted line</div>
        <div>Second <span>pasted</span> line</div>
        <p>Third pasted line</p>
      </div>
    );

    expect(getEditableTextWithLineBreaks(container.firstChild))
      .toBe("First pasted line\nSecond pasted line\nThird pasted line");
  });

  it("keeps heading and paragraph formats per line", () => {
    const element = {
      type: "heading",
      headingLevel: 1,
      content: "Main title\nSupporting copy",
      textBlockFormats: ["h1", "text"],
    };
    const { container } = render(<div>{renderRichTextBlocks(element)}</div>);

    expect(getTextBlockFormats(element)).toEqual(["h1", "text"]);
    expect(container.querySelector("h1")?.textContent).toBe("Main title");
    expect(container.querySelector("p")?.textContent).toBe("Supporting copy");
  });

  it("keeps bullets and numbers scoped to their selected lines", () => {
    const element = {
      type: "text",
      content: "Plain introduction\nSelected bullet\nPlain ending\nSelected number",
      textBlockFormats: ["text", "bullets", "text", "numbers"],
    };
    const { container } = render(<div>{renderRichTextBlocks(element)}</div>);
    const blocks = container.querySelectorAll("[data-builder-text-block]");

    expect(getTextBlockFormats(element)).toEqual(["text", "bullets", "text", "numbers"]);
    expect([...blocks].map((block) => block.dataset.builderTextBlock))
      .toEqual(["text", "bullets", "text", "numbers"]);
    expect(container.querySelectorAll('[data-builder-text-block="bullets"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-builder-text-block="numbers"]')).toHaveLength(1);
  });

  it("does not let an old whole-element font size flatten mixed blocks", () => {
    const element = {
      type: "heading",
      headingLevel: 1,
      content: "Main title\nSupporting copy",
      textBlockFormats: ["h1", "text"],
    };
    const { container } = render(
      <div>{renderRichTextBlocks(element, [{ field: "content", start: 0, end: element.content.length, fontSize: "17px" }])}</div>
    );

    expect(container.querySelector("h1 span")).toBeNull();
    expect(container.querySelector("p span")).toBeNull();
  });

  it("applies a selected font size across adjacent heading lines in a mixed-format element", () => {
    const element = {
      type: "heading",
      headingLevel: 1,
      content: "TIMELESS PHOTOGRAPHY\n\nNatalie\nAbu Allies",
      textBlockFormats: ["text", "h1", "h1", "h1"],
    };
    const selectionStart = element.content.indexOf("Natalie");
    const { container } = render(
      <div>{renderRichTextBlocks(element, [{
        field: "content",
        start: selectionStart,
        end: element.content.length,
        fontSize: "76px",
      }])}</div>
    );
    const headingSpans = container.querySelectorAll("h1 span");

    expect(headingSpans).toHaveLength(2);
    expect([...headingSpans].map((span) => span.textContent)).toEqual(["Natalie", "Abu Allies"]);
    expect([...headingSpans].every(
      (span) => span.style.fontSize === "calc(76px * var(--builder-text-fit-scale, 1))"
    )).toBe(true);
    expect(container.querySelector('p[data-builder-text-block="text"] span')).toBeNull();
  });

  it("targets only the lines touched by the selection", () => {
    const content = "First heading\nMiddle text\nLast text";

    expect(getTextBlockIndexesForRange(content, 14, 25)).toEqual([1]);
    expect(getTextBlockIndexesForRange(content, 6, 20)).toEqual([0, 1]);
  });

  it("preserves intentionally added blank editor rows", () => {
    expect(splitEditableLines("")).toEqual([""]);
    expect(splitEditableLines("\n")).toEqual(["", ""]);
    expect(splitEditableLines("Facebook\n")).toEqual(["Facebook", ""]);
  });

  it("rebuilds a selected word range across formatted spans", () => {
    const { container } = render(
      <p>Design <span>pages</span>, collect responses</p>
    );

    const range = createDomTextRange(container.querySelector("p"), 7, 12);

    expect(range.toString()).toBe("pages");
  });  it("limits selected-word effects to their saved text range", () => {
    const { container } = render(
      <h1>
        {renderRichText("Build your business", [
          {
            field: "content",
            start: 11,
            end: 19,
            fontStyle: "italic",
            fontFamily: '"EB Garamond", serif',
            opacity: "0.42",
            textDecoration: "underline",
            color: "#123456",
            backgroundColor: "rgba(254, 220, 186, 0.5)",
          },
        ])}
      </h1>
    );

    const formattedRange = container.querySelector("span");
    expect(formattedRange.textContent).toBe("business");
    expect(formattedRange.style.fontStyle).toBe("italic");
    expect(formattedRange.style.fontFamily).toBe('"EB Garamond", serif');
    expect(formattedRange.style.opacity).toBe("0.42");
    expect(formattedRange.style.textDecoration).toBe("underline");
    expect(formattedRange.style.color).toBe("rgb(18, 52, 86)");
    expect(formattedRange.style.backgroundColor).toBe("rgba(254, 220, 186, 0.5)");
    expect(container.querySelector("h1").firstChild.nodeType).toBe(Node.TEXT_NODE);
  });
  it("places the toolbar high enough to clear the element move handle", () => {
    const placement = getFloatingToolbarPlacement({
      anchorRect: { left: 350, top: 300, bottom: 320, width: 100 },
      toolbarRect: { width: 400, height: 80 },
      horizontalBounds: { left: 200, right: 800 },
      viewportHeight: 600,
    });

    expect(placement).toEqual({ left: 200, top: 192, placement: "above" });
  });

  it("moves the toolbar below and keeps it inside canvas bounds near an edge", () => {
    const placement = getFloatingToolbarPlacement({
      anchorRect: { left: 750, top: 40, bottom: 60, width: 50 },
      toolbarRect: { width: 300, height: 80 },
      horizontalBounds: { left: 200, right: 800 },
      viewportHeight: 600,
    });

    expect(placement).toEqual({ left: 500, top: 70, placement: "below" });
  });

  it("keeps the toolbar outside the full selected element", () => {
    const placement = getFloatingToolbarPlacement({
      anchorRect: { left: 90, top: 680, bottom: 704, width: 120 },
      avoidanceRect: { left: 90, top: 260, bottom: 740, width: 480 },
      toolbarRect: { width: 700, height: 80 },
      horizontalBounds: { left: 28, right: 885 },
      viewportHeight: 900,
    });

    expect(placement).toEqual({ left: 28, top: 152, placement: "above" });
  });
  it("repairs exact long-form text duplication without changing normal copy", () => {
    const original = "Design pages, collect responses, manage roles, and prepare the backend integration.";

    expect(collapseAccidentalTextDuplication(original.repeat(3))).toBe(original);
    expect(collapseAccidentalTextDuplication(original)).toBe(original);
  });
});


describe("selection move handle placement", () => {
  const bounds = { left: 12, right: 800 };
  it("uses the opposite edge from the formatting toolbar", () => {
    const result = getSelectionMoveHandlePlacement({
      elementRect: { left: 100, right: 400, top: 200, bottom: 260 },
      toolbarRect: { left: 50, right: 550, top: 80, bottom: 180 },
      horizontalBounds: bounds, viewportHeight: 600, placement: "above",
    });
    expect(result).toMatchObject({ left: 368, top: 266, edge: "below" });
  });
  it("uses a side edge when the component touches both viewport edges", () => {
    const result = getSelectionMoveHandlePlacement({
      elementRect: { left: 100, right: 400, top: 0, bottom: 600 },
      toolbarRect: { left: 100, right: 400, top: 12, bottom: 112 },
      horizontalBounds: bounds, viewportHeight: 600, placement: "above",
    });
    expect(result.edge).toBe("right");
    expect(result.left).toBeGreaterThan(400);
    expect(result.top).toBeGreaterThanOrEqual(12);
  });
  it("keeps the handle inside the canvas at the top-right corner", () => {
    const result = getSelectionMoveHandlePlacement({
      elementRect: { left: 650, right: 820, top: 5, bottom: 65 },
      toolbarRect: { left: 300, right: 800, top: 75, bottom: 175 },
      horizontalBounds: bounds, viewportHeight: 600, placement: "below",
    });
    expect(result.left).toBeGreaterThanOrEqual(12);
    expect(result.left + 32).toBeLessThanOrEqual(800);
    expect(result.top).toBeGreaterThanOrEqual(12);
    expect(result.edge).toBe("left");
  });
});


describe("editable selection block boundaries", () => {
  it("includes every block when the editable container is selected", () => {
    const root = document.createElement("div");
    root.innerHTML = '<h1 data-builder-text-block="h1">First</h1><p data-builder-text-block="text">Second</p>';
    const range = document.createRange();
    range.selectNodeContents(root);
    expect(getEditableSelectionBlockIndexes(root, range)).toEqual([0, 1]);
  });
  it("targets only the last block for a caret at the container end", () => {
    const root = document.createElement("div");
    root.innerHTML = '<p data-builder-text-block="text">First</p><p data-builder-text-block="text">Second</p>';
    const range = document.createRange();
    range.selectNodeContents(root);
    range.collapse(false);
    expect(getEditableSelectionBlockIndexes(root, range)).toEqual([1]);
  });
  it("excludes the next block when selection ends at its first character", () => {
    const root = document.createElement("div");
    root.innerHTML = '<p data-builder-text-block="text">First</p><p data-builder-text-block="text">Second</p>';
    const range = document.createRange();
    range.setStart(root.firstChild.firstChild, 0);
    range.setEnd(root.lastChild.firstChild, 0);
    expect(getEditableSelectionBlockIndexes(root, range)).toEqual([0]);
  });
});
