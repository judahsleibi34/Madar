import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import RuntimeFormToast from "./RuntimeFormToast";

describe("RuntimeFormToast", () => {
  afterEach(() => vi.useRealTimers());

  it("shows a plain user-facing error and can be dismissed", () => {
    const onDismiss = vi.fn();
    render(
      <RuntimeFormToast
        toast={{ title: "Please check the form", message: "Full name is required." }}
        onDismiss={onDismiss}
      />
    );

    expect(screen.getByRole("alert").textContent).toContain("Full name is required.");
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("dismisses itself after a short delay", () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    render(<RuntimeFormToast toast={{ message: "Try again." }} onDismiss={onDismiss} />);

    act(() => vi.advanceTimersByTime(4500));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
