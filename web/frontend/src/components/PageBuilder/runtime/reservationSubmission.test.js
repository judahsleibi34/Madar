import { describe, expect, it } from "vitest";

import {
  createReservationIdempotencyKey,
  getReservationErrorMessage,
} from "./reservationSubmission";

describe("reservation submission recovery", () => {
  it("explains unavailable group booking and invalid seat quantities", () => {
    expect(getReservationErrorMessage({ code: "reservation_capacity_unavailable" })).toContain("contact the organizer");
    expect(getReservationErrorMessage({ code: "reservation_seats_invalid" })).toContain("valid number of seats");
  });
  it("creates bounded client idempotency keys", () => {
    const first = createReservationIdempotencyKey();
    const second = createReservationIdempotencyKey();

    expect(first).toMatch(/^madar-reservation-/);
    expect(first.length).toBeLessThanOrEqual(64);
    expect(second).not.toBe(first);
  });

  it("maps stable slot and retry conflicts to recovery messages", () => {
    expect(getReservationErrorMessage({ code: "reservation_slot_unavailable" })).toContain(
      "no longer available"
    );
    expect(getReservationErrorMessage({ code: "idempotency_conflict" })).toContain(
      "original request"
    );
    expect(getReservationErrorMessage({ code: "submission_rejected" })).toContain(
      "could not be accepted"
    );
  });
});
