import { describe, expect, it } from "vitest";

import {
  findReservationBlockElement,
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

  it("keeps local data when the selected source no longer exists", () => {
    expect(resolveReservationBlockValue(stalePlacement, [])).toEqual(
      stalePlacement.reservation
    );
  });
});
