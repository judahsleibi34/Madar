import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  collapseAccidentalTextDuplication,
  createDomTextRange,
  getFloatingToolbarPlacement,
  getEditableTextWithLineBreaks,
  getTextBlockFormats,
  getTextBlockIndexesForRange,
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
  it("repairs exact long-form text duplication without changing normal copy", () => {
    const original = "Design pages, collect responses, manage roles, and prepare the backend integration.";

    expect(collapseAccidentalTextDuplication(original.repeat(3))).toBe(original);
    expect(collapseAccidentalTextDuplication(original)).toBe(original);
  });
});
