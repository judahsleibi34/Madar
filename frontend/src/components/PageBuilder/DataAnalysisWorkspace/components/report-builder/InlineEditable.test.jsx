import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import InlineEditable from "./InlineEditable";
import inlineEditableSource from "./InlineEditable.jsx?raw";

const htmlPayload = "<img src=x onerror=alert(1)><b>Safe text</b>";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("InlineEditable report text safety", () => {
  it("stores pasted HTML payloads as literal plain text", () => {
    const handleChange = vi.fn();
    document.execCommand = vi.fn((_command, _showUi, text) => {
      screen.getByRole("textbox", { name: "Report body" }).textContent = text;
      return true;
    });

    render(
      <InlineEditable
        ariaLabel="Report body"
        value=""
        multiline
        onChange={handleChange}
      />
    );

    const editable = screen.getByRole("textbox", { name: "Report body" });
    fireEvent.paste(editable, {
      clipboardData: {
        getData: () => htmlPayload,
      },
    });
    fireEvent.blur(editable);

    expect(handleChange).toHaveBeenCalledWith(htmlPayload, "auto");
    expect(editable.textContent).toBe(htmlPayload);
    expect(editable.querySelector("img")).toBeNull();
    expect(editable.querySelector("b")).toBeNull();
  });

  it("renders existing HTML-like values as visible text, not elements", () => {
    render(<InlineEditable ariaLabel="Report title" value="<b>Hello</b>" />);

    const editable = screen.getByRole("textbox", { name: "Report title" });

    expect(editable.textContent).toBe("<b>Hello</b>");
    expect(editable.querySelector("b")).toBeNull();
    expect(editable.innerHTML).toContain("&lt;b&gt;Hello&lt;/b&gt;");
  });

  it("does not use dangerouslySetInnerHTML", () => {
    expect(inlineEditableSource).not.toContain("dangerouslySetInnerHTML");
  });

  it("preserves multiline text content and blur updates", () => {
    const handleChange = vi.fn();
    const multilineValue = "First line\nSecond line";

    render(
      <InlineEditable
        ariaLabel="Report notes"
        value={multilineValue}
        multiline
        onChange={handleChange}
      />
    );

    const editable = screen.getByRole("textbox", { name: "Report notes" });
    expect(editable.textContent).toBe(multilineValue);

    editable.textContent = "Updated first line\nUpdated second line";
    fireEvent.blur(editable);

    expect(editable.textContent).toBe("Updated first line\nUpdated second line");
    expect(handleChange).toHaveBeenCalledWith(
      "Updated first line\nUpdated second line",
      "auto"
    );
  });
});
