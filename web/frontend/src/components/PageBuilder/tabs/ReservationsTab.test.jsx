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
  it.each(["restricted", "flexible"])("returns from the %s builder to reservations and keeps edits when reopening", bookingMode => {
    const update = vi.fn();
    const save = vi.fn();
    const initial = [{ ...reservationBlocks[0], element: { ...reservationBlocks[0].element, reservation: {
      ...reservationBlocks[0].element.reservation, bookingMode,
      formItems: [{ id: "intro", type: "heading", text: "Original heading" }],
    } } }];
    const props = { reservationBlocks: initial, activeReservationId: "reservation-1", onAddReservationBlock: vi.fn(),
      onSelectReservationBlock: vi.fn(), onUpdateReservationBlock: update, onDeleteReservationBlock: vi.fn(), onSave: save };
    const { container, rerender } = render(<ReservationsTab {...props} />);
    if (bookingMode === "restricted") fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    fireEvent.change(screen.getByLabelText("Heading text"), { target: { value: "Edited heading" } });
    const changed = update.mock.calls.at(-1)[1];
    rerender(<ReservationsTab {...props} reservationBlocks={[{ ...initial[0], element: { ...initial[0].element, ...changed } }]} />);
    const changesBeforeBack = update.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "Back to reservations" }));
    expect(container.querySelector(".is-form-editing")).toBeNull();
    expect(container.querySelector(".booking-element-builder")).toBeNull();
    expect(screen.getByRole("heading", { name: "Reservations", exact: true })).toBeTruthy();
    expect(update).toHaveBeenCalledTimes(changesBeforeBack);
    expect(save).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Builder/ }));
    expect(screen.getByLabelText("Heading text").value).toBe("Edited heading");
  });
  it("configures one appointment without changing another and preserves its settings when its time changes", () => {
    const update = vi.fn();
    const blocks = [{ ...reservationBlocks[0], element: { ...reservationBlocks[0].element,
      reservation: { ...reservationBlocks[0].element.reservation, timeSlotsByDate: { "2026-08-01": ["09:00", "11:00"] } } } }];
    const props = { reservationBlocks: blocks, activeReservationId: "reservation-1", onAddReservationBlock: vi.fn(),
      onSelectReservationBlock: vi.fn(), onUpdateReservationBlock: update, onDeleteReservationBlock: vi.fn() };
    const { rerender } = render(<ReservationsTab {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Edit session at 09:00 on Sat, Aug 1, 2026" }));
    fireEvent.change(screen.getByLabelText("Booking type at 09:00"), { target: { value: "group" } });
    const saved = update.mock.calls.at(-1)[1].reservation;
    expect(saved.sessionSettingsByDate).toEqual({ "2026-08-01": { "09:00": { sessionType: "group", seatCapacity: 2 } } });
    rerender(<ReservationsTab {...props} reservationBlocks={[{ ...blocks[0], element: { ...blocks[0].element, reservation: saved } }]} />);
    expect(screen.getByRole("button", { name: "Edit session at 11:00 on Sat, Aug 1, 2026" }).textContent).toBe("One-to-one · 1 person");
    fireEvent.change(screen.getByLabelText("Maximum people at 09:00"), { target: { value: "6" } });
    expect(update.mock.calls.at(-1)[1].reservation.sessionSettingsByDate["2026-08-01"]["09:00"].seatCapacity).toBe(6);
    const sixPeople = update.mock.calls.at(-1)[1].reservation;
    rerender(<ReservationsTab {...props} reservationBlocks={[{ ...blocks[0], element: { ...blocks[0].element, reservation: sixPeople } }]} />);
    fireEvent.change(screen.getByLabelText("Time 1 for Sat, Aug 1, 2026"), { target: { value: "10:00" } });
    const renamed = update.mock.calls.at(-1)[1].reservation;
    expect(renamed.sessionSettingsByDate).toEqual({ "2026-08-01": { "10:00": { sessionType: "group", seatCapacity: 6 } } });
    expect(renamed.timeSlotsByDate["2026-08-01"]).toEqual(["10:00", "11:00"]);
  });

  it("does not count placeholder times when a saved date has no appointments", () => {
    render(<ReservationsTab reservationBlocks={[{ ...reservationBlocks[0], element: { ...reservationBlocks[0].element,
      reservation: { bookingMode: "restricted", availableDates: ["2026-08-01", "2026-08-01"] } } }]}
      activeReservationId="reservation-1" onAddReservationBlock={vi.fn()} onSelectReservationBlock={vi.fn()}
      onUpdateReservationBlock={vi.fn()} onDeleteReservationBlock={vi.fn()} />);
    expect(screen.getByText("0 saved appointments across 1 date · Total capacity: 0 people")).toBeTruthy();
  });

  it("saves the weekly toggle directly and restores its state without extra controls", () => {
    const onUpdateReservationBlock = vi.fn();
    const props = { reservationBlocks, activeReservationId: "reservation-1",
      onAddReservationBlock: vi.fn(), onSelectReservationBlock: vi.fn(),
      onUpdateReservationBlock, onDeleteReservationBlock: vi.fn() };
    const { rerender } = render(<ReservationsTab {...props} />);
    fireEvent.click(screen.getByRole("checkbox", { name: "Repeat weekly" }));
    expect(onUpdateReservationBlock).toHaveBeenLastCalledWith("reservation-1", {
      reservation: expect.objectContaining({
        weeklyRepeatDates: ["2026-08-01"],
        availableDates: ["2026-08-01"],
        timeSlotsByDate: { "2026-08-01": ["09:00"] },
      }),
    });
    const updated = onUpdateReservationBlock.mock.calls.at(-1)[1].reservation;
    rerender(<ReservationsTab {...props} reservationBlocks={[{
      ...reservationBlocks[0], element: { ...reservationBlocks[0].element, reservation: updated },
    }]} />);
    expect(screen.getByRole("checkbox", { name: "Repeat weekly" }).checked).toBe(true);
    expect(screen.getByText("1 saved appointment across 1 date · Total capacity: 1 person")).toBeTruthy();
    expect(screen.getByText("Weekly repeats are enabled. Future repeats are additional to these saved appointments.")).toBeTruthy();
    expect(screen.queryByLabelText("Repeat until")).toBeNull();
    expect(screen.queryByRole("button", { name: "Add dates" })).toBeNull();
    fireEvent.click(screen.getByRole("checkbox", { name: "Repeat weekly" }));
    expect(onUpdateReservationBlock.mock.calls.at(-1)[1].reservation.weeklyRepeatDates).toEqual([]);
  });
  it("guides users through the booking-element builder and availability", () => {
    const onUpdateReservationBlock = vi.fn();
    const onAddReservationBlock = vi.fn();
    const onSave = vi.fn();
    const { container } = render(
      <ReservationsTab
        reservationBlocks={reservationBlocks}
        activeReservationId="reservation-1"
        onAddReservationBlock={onAddReservationBlock}
        onSave={onSave}
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
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onAddReservationBlock).not.toHaveBeenCalled();
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
    expect(document.activeElement).toBe(screen.getByRole("button", { name: /choose a date/i }));

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

    fireEvent.click(screen.getByRole("button", { name: /^Heading/ }));
    const [, updates] = onUpdateReservationBlock.mock.calls.at(-1);
    expect(updates.reservation.formItems[0]).toEqual(expect.objectContaining({ type: "heading" }));
  });

  it("edits and removes one date without changing another date's times", () => {
    const onUpdateReservationBlock = vi.fn();
    const blocks = [{
      ...reservationBlocks[0],
      element: {
        ...reservationBlocks[0].element,
        reservation: {
          ...reservationBlocks[0].element.reservation,
          availableDates: ["2026-08-01", "2026-08-02"],
          timeSlotsByDate: { "2026-08-01": ["09:00"], "2026-08-02": ["14:30", "16:00"] },
        },
      },
    }];
    render(<ReservationsTab
      reservationBlocks={blocks}
      activeReservationId="reservation-1"
      onAddReservationBlock={vi.fn()}
      onSelectReservationBlock={vi.fn()}
      onUpdateReservationBlock={onUpdateReservationBlock}
      onDeleteReservationBlock={vi.fn()}
    />);
    fireEvent.click(screen.getByRole("button", { name: /2 time slots.*Sun, Aug 2, 2026/ }));
    fireEvent.change(screen.getByLabelText("Time 1 for Sun, Aug 2, 2026"), { target: { value: "15:00" } });
    expect(onUpdateReservationBlock.mock.calls.at(-1)[1].reservation.timeSlotsByDate).toEqual({
      "2026-08-01": ["09:00"], "2026-08-02": ["15:00", "16:00"],
    });
    fireEvent.click(screen.getByRole("button", { name: "Remove Sun, Aug 2, 2026" }));
    expect(onUpdateReservationBlock.mock.calls.at(-1)[1].reservation).toEqual(expect.objectContaining({
      availableDates: ["2026-08-01"], timeSlotsByDate: { "2026-08-01": ["09:00"] },
    }));
  });
});
