import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PhotoProofingBlock from "./PhotoProofingBlock";

const content = `First portrait
Window light
https://images.example/first.jpg

Second portrait
Golden hour
https://images.example/second.jpg`;

beforeEach(() => {
  vi.useFakeTimers();
  HTMLElement.prototype.setPointerCapture = vi.fn();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("PhotoProofingBlock", () => {
  it("opens the proofing modal and advances after a right drag", () => {
    const { container } = render(<PhotoProofingBlock content={content} />);
    fireEvent.click(screen.getByRole("button", { name: "Start selecting" }));
    expect(screen.getByRole("dialog", { name: "Choose your photos" })).toBeTruthy();
    expect(screen.getByAltText("First portrait")).toBeTruthy();

    const card = document.querySelector(".photo-proofing-card");
    fireEvent.pointerDown(card, { pointerId: 1, clientX: 100 });
    fireEvent.pointerMove(card, { pointerId: 1, clientX: 230 });
    fireEvent.pointerUp(card, { pointerId: 1, clientX: 230 });
    act(() => vi.advanceTimersByTime(250));

    expect(screen.getByAltText("Second portrait")).toBeTruthy();
    expect(container.querySelector(".photo-proofing-launcher")).toBeTruthy();
  });
});
