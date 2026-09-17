import { cleanup, render } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import SelectionBoundary from "./PageBuilder.selectionBoundary";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it("tracks the actual text box dimensions without changing the artwork layer", () => {
  let resize;
  const disconnect = vi.fn();
  vi.stubGlobal("ResizeObserver", class {
    constructor(callback) { resize = callback; }
    observe() {}
    disconnect() { disconnect(); }
  });
  let width = 420;
  let height = 120;
  vi.spyOn(HTMLElement.prototype, "offsetWidth", "get").mockImplementation(() => width);
  vi.spyOn(HTMLElement.prototype, "offsetHeight", "get").mockImplementation(() => height);
  const { container, unmount } = render(<div>
    <div data-builder-element-id="heading" style={{ zIndex: 1 }} />
    <SelectionBoundary elementId="heading" frameStyle={{ position: "absolute", transform: "translate3d(40px, 60px, 0)", width: "400px", height: "80px" }}>
      <button aria-label="Resize heading" />
    </SelectionBoundary>
    <div data-builder-element-id="image" style={{ zIndex: 1 }} />
  </div>);
  const boundary = container.querySelector("[data-selection-for]");
  expect(boundary.style.width).toBe("420px");
  expect(boundary.style.height).toBe("120px");
  expect(boundary.style.transform).toBe("translate3d(40px, 60px, 0)");
  expect(Number(boundary.style.zIndex)).toBeGreaterThan(1);
  expect(container.querySelector('[data-builder-element-id="heading"]').style.zIndex).toBe("1");
  width = 320; height = 180; resize();
  expect(boundary.style.width).toBe("320px");
  expect(boundary.style.height).toBe("180px");
  unmount();
  expect(disconnect).toHaveBeenCalled();
});
