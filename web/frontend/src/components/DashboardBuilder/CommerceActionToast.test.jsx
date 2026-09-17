import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import CommerceActionToast from "./CommerceActionToast";
import { notifyCommerceAction } from "../../utils/commerceActionToast";

afterEach(() => { cleanup(); vi.useRealTimers(); });

describe("commerce action feedback", () => {
  it("keeps completion feedback after page content changes and dismisses queued actions in order", () => {
    vi.useFakeTimers();
    const { rerender } = render(<><CommerceActionToast /><p>Product editor</p></>);
    act(() => notifyCommerceAction({ type: "success", title: "Product saved" }));
    rerender(<><CommerceActionToast /><p>Products</p></>);
    expect(screen.getByRole("alert").textContent).toContain("Product saved");
    act(() => notifyCommerceAction({ type: "error", title: "Could not load orders" }));
    act(() => vi.advanceTimersByTime(4200));
    expect(screen.getByRole("alert").textContent).toContain("Could not load orders");
    act(() => vi.advanceTimersByTime(4200));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
