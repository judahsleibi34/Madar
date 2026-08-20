import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AutoFitDirectText from "./PageBuilder.autoFitText";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AutoFitDirectText", () => {
  it("preserves an explicitly chosen heading size instead of scaling it down", () => {
    const requestAnimationFrame = vi.fn();
    vi.stubGlobal("requestAnimationFrame", requestAnimationFrame);
    vi.stubGlobal("cancelAnimationFrame", vi.fn());

    render(
      <div className="direct-element-frame">
        <AutoFitDirectText
          preserveFontSize
          as="h1"
          className="builder-element-heading"
          fitKey="manual-heading-size"
          style={{ fontSize: "75px", "--builder-text-fit-scale": "0.5" }}
        >
          Natalie Abu Allies
        </AutoFitDirectText>
      </div>
    );

    const heading = screen.getByRole("heading");
    expect(heading.style.fontSize).toBe("75px");
    expect(heading.style.getPropertyValue("--builder-text-fit-scale")).toBe("");
    expect(requestAnimationFrame).not.toHaveBeenCalled();
  });

  it("shrinks direct-layout text until all content fits inside its frame", () => {
    let scheduledFit = null;
    vi.stubGlobal("requestAnimationFrame", (callback) => {
      scheduledFit = callback;
      return 1;
    });
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    vi.stubGlobal("ResizeObserver", class ResizeObserver {
      observe() {}
      disconnect() {}
    });

    render(
      <div className="direct-element-frame">
        <AutoFitDirectText
          as="h1"
          className="builder-element-heading"
          fitKey="long-heading"
          style={{ fontSize: "48px" }}
        >
          Build your business app without code
        </AutoFitDirectText>
      </div>
    );

    const heading = screen.getByRole("heading");
    Object.defineProperties(heading, {
      clientWidth: { configurable: true, value: 320 },
      clientHeight: { configurable: true, value: 64 },
      scrollWidth: { configurable: true, get: () => 320 },
      scrollHeight: {
        configurable: true,
        get: () => {
          const fittedSize = Number.parseFloat(
            heading.style.getPropertyValue("--builder-fitted-font-size")
          );
          return fittedSize > 24 || !fittedSize ? 128 : 60;
        },
      },
    });

    scheduledFit();

    expect(
      Number.parseFloat(heading.style.getPropertyValue("--builder-fitted-font-size"))
    ).toBeLessThanOrEqual(24);
    expect(
      Number.parseFloat(heading.style.getPropertyValue("--builder-text-fit-scale"))
    ).toBeLessThan(1);
  });
});
