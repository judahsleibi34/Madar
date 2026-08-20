// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ReservationsTab from "./ReservationsTab";

afterEach(cleanup);

const reservationBlocks = [
  {
    page: { id: "home", name: "Home" },
    section: { id: "section-1", name: "Bookings" },
    element: {
      id: "reservation-1",
      name: "Appointments",
      reservation: {
        title: "Book an appointment",
        bookingMode: "restricted",
        services: ["Consultation", "Follow-up"],
        availableDates: ["2026-08-01"],
        timeSlots: ["09:00"],
      },
    },
  },
];

describe("ReservationsTab structure", () => {
  it("guides users through the booking-element builder and availability", () => {
    const onUpdateReservationBlock = vi.fn();
    const onAddReservationBlock = vi.fn();
    const { container } = render(
      <ReservationsTab
        reservationBlocks={reservationBlocks}
        activeReservationId="reservation-1"
        onAddReservationBlock={onAddReservationBlock}
        onOpenReservationBlock={vi.fn()}
        onSelectReservationBlock={vi.fn()}
        onUpdateReservationBlock={onUpdateReservationBlock}
        onDeleteReservationBlock={vi.fn()}
      />
    );

    expect(screen.getByLabelText("Reservation setup steps")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Appointments/ })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Reservation build name"), { target: { value: "VIP bookings" } });
    expect(onUpdateReservationBlock).toHaveBeenCalledWith("reservation-1", { name: "VIP bookings" });
    fireEvent.click(screen.getByRole("button", { name: "Save as new build" }));
    expect(onAddReservationBlock).toHaveBeenCalledWith(expect.objectContaining({
      name: "Appointments copy 2",
      reservation: expect.objectContaining({ bookingMode: "restricted" }),
    }));
    expect(container.querySelector(".reservation-editor-card.is-restricted")).toBeTruthy();
    expect(container.querySelector(".reservation-copy-section")).toBeNull();
    expect(container.querySelector(".reservation-block-builder-section")).toBeNull();
    expect(container.querySelectorAll(".reservation-schedule-section")).toHaveLength(2);
    expect(screen.queryByRole("button", { name: /Details Name and public text/ })).toBeNull();
    expect(container.querySelector('input[type="date"]')).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /choose a date/i }));
    expect(screen.getByRole("dialog", { name: "Choose an available date" })).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Choose an available date" })).toBeNull();

    const dateTimeInput = screen.getByLabelText("Time 1 for Sat, Aug 1, 2026");
    fireEvent.change(dateTimeInput, { target: { value: "11:30" } });
    const [, availabilityUpdate] = onUpdateReservationBlock.mock.calls.at(-1);
    expect(availabilityUpdate.reservation.timeSlotsByDate).toEqual({
      "2026-08-01": ["11:30"],
    });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(container.querySelector(".reservation-block-builder-section")).toBeTruthy();
    expect(container.querySelectorAll(".reservation-schedule-section")).toHaveLength(0);
    expect(screen.getByText("Book an appointment")).toBeTruthy();
    expect(screen.getByLabelText("Booking component toolbox")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /Heading/ }));
    const [, updates] = onUpdateReservationBlock.mock.calls.at(-1);
    expect(updates.reservation.formItems[0]).toEqual(expect.objectContaining({ type: "heading" }));
  });
});