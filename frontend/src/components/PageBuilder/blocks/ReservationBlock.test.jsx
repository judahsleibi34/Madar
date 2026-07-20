// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ReservationBlock from "./ReservationBlock";

afterEach(cleanup);

describe("ReservationBlock fixed slots", () => {
  it("submits a selected configured date and time", async () => {
    const onSubmit = vi.fn().mockResolvedValue(false);
    const { container } = render(
      <ReservationBlock
        bookingMode="restricted"
        availableDates={["2026-07-14", "2026-07-15"]}
        timeSlots={["12:00", "17:00"]}
        services={["Consultation"]}
        submitLabel="Book slot"
        onSubmit={onSubmit}
      />
    );

    expect(container.querySelector('input[type="date"]')).toBeNull();
    expect(container.querySelector('input[type="time"]')).toBeNull();
    expect(screen.queryByLabelText("Service")).toBeNull();
    expect(screen.queryByLabelText("Guests")).toBeNull();
    expect(container.querySelector(".reservation-summary")).toBeNull();
    expect(screen.queryByText("Reservation")).toBeNull();

    const slot = screen.getByRole("button", { name: /July 14, 2026 at 12:00 PM/i });
    fireEvent.click(slot);
    expect(slot.getAttribute("aria-pressed")).toBe("true");

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Madar User" } });
    fireEvent.change(screen.getByLabelText("Contact"), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Book slot" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toEqual(expect.objectContaining({
      date: "2026-07-14",
      time: "12:00",
      service: "Consultation",
    }));
  });

  it("keeps free date and time inputs for visitor date requests", () => {
    const { container } = render(<ReservationBlock bookingMode="flexible" />);

    expect(container.querySelector('input[type="date"]')).toBeTruthy();
    expect(container.querySelector('input[type="time"]')).toBeTruthy();
    expect(container.querySelector(".fixed-slot-picker")).toBeNull();
    expect(screen.getByRole("heading", { name: "Your details" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Appointment details" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Additional notes" })).toBeTruthy();
    expect(screen.queryByLabelText("Guests")).toBeNull();
    expect(container.querySelector(".reservation-summary")).toBeNull();
  });
});
