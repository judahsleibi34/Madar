// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ReservationsTab from "./ReservationsTab";

afterEach(cleanup);

describe("ReservationsTab structure", () => {
  it("guides users through one reservation setup step at a time", () => {
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

    const { container } = render(
      <ReservationsTab
        reservationBlocks={reservationBlocks}
        activeReservationId="reservation-1"
        onAddReservationBlock={vi.fn()}
        onOpenReservationBlock={vi.fn()}
        onSelectReservationBlock={vi.fn()}
        onUpdateReservationBlock={vi.fn()}
        onDeleteReservationBlock={vi.fn()}
      />
    );

    expect(screen.getByLabelText("Reservation setup steps")).toBeTruthy();
    expect(container.querySelector(".reservation-editor-card.is-restricted")).toBeTruthy();
    expect(container.querySelector(".reservation-copy-section")).toBeTruthy();
    expect(screen.queryByLabelText("Reservation booking mode")).toBeNull();
    expect(container.querySelector(".reservation-services-section")).toBeNull();
    expect(container.querySelectorAll(".reservation-schedule-section")).toHaveLength(0);

    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(container.querySelector(".reservation-copy-section")).toBeNull();
    expect(container.querySelector(".reservation-services-section")).toBeNull();
    expect(container.querySelectorAll(".reservation-schedule-section")).toHaveLength(2);
    expect(container.querySelector('input[type="date"]')).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /choose a date/i }));
    expect(screen.getByRole("dialog", { name: "Choose an available date" })).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog", { name: "Choose an available date" })).toBeNull();
  });
});
