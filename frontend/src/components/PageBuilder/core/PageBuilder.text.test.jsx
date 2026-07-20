import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  collapseAccidentalTextDuplication,
  createDomTextRange,
  getFloatingToolbarPlacement,
  renderRichText,
} from "./PageBuilder.text";

afterEach(cleanup);

describe("renderRichText", () => {
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
    expect(formattedRange.style.textDecoration).toBe("underline");
    expect(formattedRange.style.color).toBe("rgb(18, 52, 86)");
    expect(formattedRange.style.backgroundColor).toBe("rgba(254, 220, 186, 0.5)");
    expect(container.querySelector("h1").firstChild.nodeType).toBe(Node.TEXT_NODE);
  });
  it("places the toolbar above selected words when space is available", () => {
    const placement = getFloatingToolbarPlacement({
      anchorRect: { left: 350, top: 300, bottom: 320, width: 100 },
      toolbarRect: { width: 400, height: 80 },
      horizontalBounds: { left: 200, right: 800 },
      viewportHeight: 600,
    });

    expect(placement).toEqual({ left: 200, top: 210, placement: "above" });
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