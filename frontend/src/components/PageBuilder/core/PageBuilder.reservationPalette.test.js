import { describe, expect, it } from "vitest";

import { elementTypes } from "./PageBuilder.constants";

describe("reservation section components", () => {
  it("offers both booking types instead of a generic reservation component", () => {
    const bookingTypes = elementTypes.filter((item) => item.group === "Bookings");

    expect(bookingTypes).toEqual([
      { id: "reservationRequest", label: "Date request", group: "Bookings" },
      { id: "reservationFixedSlots", label: "Fixed slots", group: "Bookings" },
    ]);
    expect(elementTypes.some((item) => item.id === "reservationBlock")).toBe(false);
  });
});
