import { describe, expect, it } from "vitest";
import { getReservationLayout, getReservationLayoutStyle, normalizeReservationLayout } from "./reservationLayout";
import { normalizeReservationFormItems } from "./reservationForm";

describe("responsive booking component layouts", () => {
  it("does not render obsolete drag spacing or fixed row heights while preserving stored metadata", () => {
    const item = { layout: { desktop: { columns: 6, position: "center", minHeight: 400, spaceAbove: 120, spaceBelow: 80 } } };
    const style = getReservationLayoutStyle(item);
    expect(style["--booking-desktop-span"]).toBe(6);
    expect(style["--booking-desktop-start"]).toBe(4);
    expect(style["--booking-desktop-height"]).toBeUndefined();
    expect(style["--booking-desktop-above"]).toBeUndefined();
    expect(style["--booking-desktop-below"]).toBeUndefined();
    expect(style["--booking-desktop-content-height"]).toBe("auto");
    expect(getReservationLayout(item).spaceAbove).toBe(120);
  });
  it("preserves explicit resize height independently of obsolete spacing and device defaults", () => {
    const [item] = normalizeReservationFormItems([{ id: "send", type: "button", label: "Send", layout: {
      desktop: { columns: 6, contentHeight: 72, spaceAbove: 120 }, mobile: { columns: 12 },
    } }]);
    expect(getReservationLayoutStyle(item)["--booking-desktop-content-height"]).toBe("72px");
    expect(getReservationLayoutStyle(item)["--booking-mobile-content-height"]).toBe("auto");
    expect(getReservationLayout(JSON.parse(JSON.stringify(item))).contentHeight).toBe(72);
  });
  it("persists horizontal positions and clamps them when width grows", () => {
    const layout = { desktop: { columns: 4, position: "custom", startColumn: 6 }, mobile: { columns: 6, position: "custom", startColumn: 99 } };
    const [saved] = normalizeReservationFormItems(JSON.parse(JSON.stringify([{ id: "name", type: "text", layout }])));
    expect(saved.layout.desktop.startColumn).toBe(6);
    expect(saved.layout.mobile.startColumn).toBe(7);
    expect(getReservationLayoutStyle(saved)["--booking-desktop-start"]).toBe(6);
    expect(normalizeReservationLayout({ desktop: { ...layout.desktop, columns: 12 } }).desktop.startColumn).toBe(1);
  });
  it("keeps legacy forms full width, inherits desktop on tablet and stacks mobile automatically", () => {
    expect(getReservationLayout({}, "desktop").columns).toBe(12);
    const item = { layout: { desktop: { columns: 6, position: "end", minHeight: 80 } } };
    expect(getReservationLayout(item, "tablet").columns).toBe(6);
    expect(getReservationLayout(item, "mobile").columns).toBe(12);
    expect(getReservationLayoutStyle(item)).toMatchObject({ "--booking-desktop-span": 6, "--booking-desktop-start": 7,
      "--booking-mobile-span": 12, "--booking-mobile-start": "auto" });
  });
  it("bounds layout input, rejects invalid modes, and preserves independent views through serialization", () => {
    const layout = normalizeReservationLayout({ desktop: { columns: 99, minHeight: -10, spaceAbove: 50000, position: "absolute" }, tablet: [],
      mobile: { columns: 6, position: "center", spaceBelow: 12 }, unknown: { columns: 1 } });
    expect(layout.desktop).toEqual({ columns: 12, minHeight: 0, spaceAbove: 10000, spaceBelow: 0, position: "auto" });
    expect(layout.tablet).toBeUndefined();
    expect(layout.unknown).toBeUndefined();
    const [saved] = normalizeReservationFormItems(JSON.parse(JSON.stringify([{ id: "name", type: "text", label: "Name", layout }])));
    expect(saved.layout).toEqual(layout);
    expect(getReservationLayoutStyle(saved)["--booking-mobile-start"]).toBe(4);
  });
});
