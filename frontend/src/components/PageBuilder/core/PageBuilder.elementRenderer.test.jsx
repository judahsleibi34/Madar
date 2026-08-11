import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createElementRenderer } from "./PageBuilder.elementRenderer";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

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

describe("video rendering", () => {
  it("defers the video source until it is near the viewport", async () => {
    let intersectionCallback;
    vi.stubGlobal("IntersectionObserver", class {
      constructor(callback) {
        intersectionCallback = callback;
      }
      observe() {}
      disconnect() {}
    });

    const renderElement = createElementRenderer({
      carouselElementTypes: new Set(),
      selected: { type: "", id: "" },
      preview: true,
      getFreeElementStyle: () => ({}),
      getElementStyle: () => ({}),
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

    render(renderElement({
      id: "video-1",
      type: "video",
      name: "Product demo",
      content: "https://media.example.com/product-demo.mp4",
      styles: {},
      video: { controls: true },
    }));

    const video = screen.getByLabelText("Product demo");
    expect(video.getAttribute("src")).toBeNull();
    intersectionCallback([{ isIntersecting: true }]);
    await waitFor(() => expect(video.getAttribute("src")).toContain(".mp4"));
    expect(video.preload).toBe("metadata");
    expect(video.playsInline).toBe(true);
  });
});

describe("document rendering", () => {
  it("shows upload guidance instead of a restricted Open button before a file exists", () => {
    const renderElement = createElementRenderer({
      carouselElementTypes: new Set(),
      selected: { type: "element", id: "document-empty" },
      preview: false,
      getFreeElementStyle: () => ({}),
      getElementStyle: () => ({}),
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

    render(renderElement({
      id: "document-empty",
      type: "document",
      content: "",
      document: { title: "View document" },
      styles: {},
    }));

    expect(screen.getByText("Upload first")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /open/i })).toBeNull();
  });

  it("opens a PDF in an accessible modal in preview mode", () => {
    const renderElement = createElementRenderer({
      carouselElementTypes: new Set(),
      selected: { type: "", id: "" },
      preview: true,
      getFreeElementStyle: () => ({}),
      getElementStyle: () => ({}),
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

    render(renderElement({
      id: "document-1",
      type: "document",
      content: "https://media.example.com/session-guide.pdf",
      assetFileName: "session-guide.pdf",
      documentMimeType: "application/pdf",
      document: { title: "Session guide", description: "Everything clients need." },
      styles: {},
    }));

    fireEvent.click(screen.getByRole("button", { name: /open/i }));

    expect(screen.getByRole("dialog", { name: "Session guide" })).toBeTruthy();
    expect(screen.getByTitle("Session guide").getAttribute("src")).toContain("session-guide.pdf");
  });

  it("passes a managed PDF URL to the document viewer", () => {
    const renderElement = createElementRenderer({
      carouselElementTypes: new Set(),
      selected: { type: "", id: "" },
      preview: true,
      getFreeElementStyle: () => ({}),
      getElementStyle: () => ({}),
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

    render(renderElement({
      id: "document-managed",
      type: "document",
      content: "/uploads/tenant_7/builder_assets/56fee3e0f73c4110abdf423d501fb835.pdf",
      assetFileName: "guide.pdf",
      documentMimeType: "application/pdf",
      document: { title: "Managed guide" },
      styles: {},
    }));

    fireEvent.click(screen.getByRole("button", { name: /open/i }));

    expect(screen.getByTitle("Managed guide").getAttribute("src")).toMatch(
      /\/uploads\/tenant_7\/builder_assets\/56fee3e0f73c4110abdf423d501fb835\.pdf\?v=3$/
    );
  });

  it("opens the viewer from the editing canvas without starting a drag", () => {
    const startDrag = vi.fn();
    const renderElement = createElementRenderer({
      carouselElementTypes: new Set(),
      selected: { type: "element", id: "document-1" },
      preview: false,
      getFreeElementStyle: () => ({}),
      getElementStyle: () => ({}),
      startDrag,
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

    render(renderElement({
      id: "document-1",
      type: "document",
      content: "https://media.example.com/guide.pdf",
      assetFileName: "guide.pdf",
      documentMimeType: "application/pdf",
      document: { title: "Guide" },
      styles: {},
    }));

    const openButton = screen.getByRole("button", { name: /open/i });
    fireEvent.pointerDown(openButton);
    fireEvent.click(openButton);

    expect(startDrag).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Guide" })).toBeTruthy();
  });
});
