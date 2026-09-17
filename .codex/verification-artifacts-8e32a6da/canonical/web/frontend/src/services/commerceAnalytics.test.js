import { afterEach, describe, expect, it, vi } from "vitest";

import { COMMERCE_EVENT_NAMES, trackCommerceEvent, trackPurchaseOnce } from "./commerceAnalytics";

const flush = () => new Promise((resolve) => queueMicrotask(resolve));

afterEach(() => {
  delete window.madarAnalytics;
  sessionStorage.clear();
  vi.restoreAllMocks();
});

describe("commerce analytics adapter", () => {
  it("supports every baseline event and strips customer PII", async () => {
    const received = [];
    window.addEventListener("madar:commerce", (event) => received.push(event.detail), { once: true });
    expect(COMMERCE_EVENT_NAMES).toEqual(expect.arrayContaining(["view_item_list", "view_item", "add_to_cart", "remove_from_cart", "view_cart", "begin_checkout", "purchase", "promotion_view", "promotion_click"]));
    expect(trackCommerceEvent("add_to_cart", { product_id: "p1", variant_id: "v1", currency: "ILS", email: "private@example.com", customer_phone: "000", address: { street: "Hidden" } })).toBe(true);
    await flush();
    expect(received[0]).toEqual({ event: "add_to_cart", payload: { product_id: "p1", variant_id: "v1", currency: "ILS" } });
  });

  it("swallows provider exceptions without blocking the caller", async () => {
    window.madarAnalytics = { track: vi.fn(() => { throw new Error("offline"); }) };
    expect(() => trackCommerceEvent("view_cart", { item_count: 2, currency: "ILS" })).not.toThrow();
    await flush();
    expect(window.madarAnalytics.track).toHaveBeenCalledOnce();
  });

  it("fires purchase only for a durable result and deduplicates reloads", async () => {
    const listener = vi.fn();
    window.addEventListener("madar:commerce", listener);
    expect(trackPurchaseOnce(null)).toBe(false);
    const order = { id: "order-1", subtotal: 20, discount_total: 2, total: 18, currency: "ILS", email: "hidden@example.com" };
    expect(trackPurchaseOnce(order, [{ product_id: "p1", variant_id: null, quantity: 1 }], "ar")).toBe(true);
    expect(trackPurchaseOnce(order, [], "ar")).toBe(false);
    await flush();
    expect(listener).toHaveBeenCalledOnce();
    expect(listener.mock.calls[0][0].detail.payload).not.toHaveProperty("email");
    window.removeEventListener("madar:commerce", listener);
  });
});
