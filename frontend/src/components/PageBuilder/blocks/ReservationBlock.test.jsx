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

    expect(screen.getByLabelText("Appointment date").value).toBe("2026-07-14");
    fireEvent.change(screen.getByLabelText("Full name *"), { target: { value: "Madar User" } });
    fireEvent.change(screen.getByLabelText("Email address *"), { target: { value: "user@example.com" } });
    fireEvent.change(screen.getByLabelText("Phone number *"), { target: { value: "+972599000000" } });
    fireEvent.click(screen.getByRole("button", { name: "Book slot" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toEqual(expect.objectContaining({
      date: "2026-07-14",
      time: "12:00",
      email: "user@example.com",
      phone: "+972599000000",
      contact: "+972599000000",
      service: "Consultation",
    }));
  });

  it("updates the public choices when Reservations-page slots change", async () => {
    const { rerender } = render(
      <ReservationBlock
        bookingMode="restricted"
        availableDates={["2026-07-14"]}
        timeSlots={["09:00"]}
      />
    );

    expect(screen.getByRole("button", { name: /July 14, 2026 at 9:00 AM/i })).toBeTruthy();

    rerender(
      <ReservationBlock
        bookingMode="restricted"
        availableDates={["2026-07-20"]}
        timeSlots={["14:30"]}
      />
    );

    await waitFor(() => expect(screen.getByLabelText("Appointment date").value).toBe("2026-07-20"));
    expect(screen.getByRole("button", { name: /July 20, 2026 at 2:30 PM/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /July 14, 2026 at 9:00 AM/i })).toBeNull();
  });

  it("keeps free date and time inputs for visitor date requests", () => {
    const { container } = render(<ReservationBlock bookingMode="flexible" />);

    expect(container.querySelector('input[type="date"]')).toBeTruthy();
    expect(container.querySelector('input[type="time"]')).toBeTruthy();
    expect(container.querySelector(".fixed-slot-picker")).toBeNull();
    expect(screen.getByRole("heading", { name: "Your details" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Appointment details" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Additional notes" })).toBeTruthy();
    expect(screen.queryByLabelText("Service")).toBeNull();
    expect(screen.queryByLabelText("Guests")).toBeNull();
    expect(container.querySelector(".reservation-summary")).toBeNull();
  });

  it("renders only explicitly configured appointment fields", () => {
    render(
      <ReservationBlock
        bookingMode="flexible"
        fields={["service", "date"]}
        services={["Planning session"]}
      />
    );

    expect(screen.queryByLabelText("Service")).toBeNull();
    expect(screen.getByLabelText("Date")).toBeTruthy();
    expect(screen.queryByLabelText("Name")).toBeNull();
    expect(screen.queryByLabelText("Contact")).toBeNull();
    expect(screen.queryByLabelText("Time")).toBeNull();
    expect(screen.queryByLabelText("Notes")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Your details" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Additional notes" })).toBeNull();
  });
});
