import { act, cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PageBuilderMeasuredFrame from "./PageBuilderMeasuredFrame";

describe("PageBuilderMeasuredFrame", () => {
  let observerCallback;
  let disconnect;

  beforeEach(() => {
    vi.useFakeTimers();
    disconnect = vi.fn();
    observerCallback = null;
    vi.stubGlobal("ResizeObserver", class ResizeObserver {
      constructor(callback) {
        observerCallback = callback;
      }
      observe() {}
      disconnect() { disconnect(); }
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("coalesces observer bursts and ignores identical measured heights", () => {
    const onMeasuredHeight = vi.fn();
    const { container } = render(
      <PageBuilderMeasuredFrame measureEnabled measurementKey="form:desktop" onMeasuredHeight={onMeasuredHeight}>
        <div className="direct-element-content">Form</div>
      </PageBuilderMeasuredFrame>
    );
    const content = container.querySelector(".direct-element-content");
    Object.defineProperty(content, "scrollHeight", { configurable: true, value: 480 });

    act(() => vi.advanceTimersByTime(100));
    expect(onMeasuredHeight).toHaveBeenCalledTimes(1);
    expect(onMeasuredHeight).toHaveBeenLastCalledWith(480);

    act(() => {
      observerCallback();
      observerCallback();
      observerCallback();
      vi.advanceTimersByTime(30);
    });
    expect(onMeasuredHeight).toHaveBeenCalledTimes(1);
  });

  it("disconnects the scoped observer when measurement is disabled", () => {
    const { rerender } = render(
      <PageBuilderMeasuredFrame measureEnabled measurementKey="form:desktop" onMeasuredHeight={vi.fn()}>
        <div className="direct-element-content">Form</div>
      </PageBuilderMeasuredFrame>
    );
    act(() => vi.advanceTimersByTime(100));

    rerender(
      <PageBuilderMeasuredFrame measureEnabled={false} measurementKey="form:desktop" onMeasuredHeight={vi.fn()}>
        <div className="direct-element-content">Form</div>
      </PageBuilderMeasuredFrame>
    );

    expect(disconnect).toHaveBeenCalledTimes(1);
  });
});
