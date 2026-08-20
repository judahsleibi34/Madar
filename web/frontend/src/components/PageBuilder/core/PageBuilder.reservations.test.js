import { describe, expect, it } from "vitest";

import {
  createReservationPalettePlacement,
  findReservationBlockElement,
  getReservationPaletteItems,
  resolveReservationBlockElement,
  resolveReservationBlockValue,
} from "./PageBuilder.reservations";

const source = {
  id: "reservation-source",
  type: "reservationBlock",
  reservation: {
    title: "Current saved title",
    services: ["Planning"],
    availableDates: ["2026-08-21"],
    timeSlots: ["14:30"],
  },
};

const stalePlacement = {
  id: "reservation-placement",
  type: "reservationBlock",
  connectedReservationBlockId: source.id,
  reservation: {
    title: "Old copied title",
    services: ["Consultation"],
    availableDates: ["2026-07-08"],
    timeSlots: ["09:00"],
  },
};

const pages = [
  {
    id: "home",
    sections: [
      {
        id: "direct",
        freeElements: [stalePlacement],
      },
      {
        id: "columns",
        rows: [{ columns: [{ elements: [source] }] }],
      },
    ],
  },
];

describe("reservation block source resolution", () => {
  it("finds reservation definitions in direct and column layouts", () => {
    expect(findReservationBlockElement(pages, source.id)).toBe(source);
    expect(findReservationBlockElement(pages, stalePlacement.id)).toBe(stalePlacement);
  });

  it("uses the selected reservation source instead of a stale placement snapshot", () => {
    expect(resolveReservationBlockElement(stalePlacement, pages)).toBe(source);
    expect(resolveReservationBlockValue(stalePlacement, pages)).toEqual(source.reservation);
  });

  it("creates exact palette entries from configured reservation definitions", () => {
    expect(getReservationPaletteItems([
      { element: source },
      {
        element: {
          id: "request-source",
          type: "reservationBlock",
          name: "Discovery call",
          reservation: { bookingMode: "flexible" },
        },
      },
    ])).toEqual([
      {
        id: source.id,
        label: source.reservation.title,
        mode: "restricted",
        type: "reservationFixedSlots",
        helper: "Fixed slots",
      },
      {
        id: "request-source",
        label: "Discovery call",
        mode: "flexible",
        type: "reservationRequest",
        helper: "Date request",
      },
    ]);
  });
  it("creates a linked placement for the exact selected saved build", () => {
    expect(createReservationPalettePlacement([{ element: source }], source.id)).toEqual({
      type: "reservationFixedSlots",
      overrides: expect.objectContaining({
        connectedReservationBlockId: source.id,
        reservationPlacementType: "restricted",
        reservation: source.reservation,
      }),
    });
  });
  it("keeps local data when the selected source no longer exists", () => {
    expect(resolveReservationBlockValue(stalePlacement, [])).toEqual(
      stalePlacement.reservation
    );
  });
});
