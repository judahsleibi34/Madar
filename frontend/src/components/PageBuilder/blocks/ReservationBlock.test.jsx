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

  it("shows only the times assigned to the selected date", () => {
    render(
      <ReservationBlock
        bookingMode="restricted"
        availableDates={["2026-07-14", "2026-07-15"]}
        timeSlots={["09:00", "16:00"]}
        timeSlotsByDate={{
          "2026-07-14": ["09:00"],
          "2026-07-15": ["16:00"],
        }}
      />
    );

    expect(screen.getByRole("button", { name: /July 14, 2026 at 9:00 AM/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /July 14, 2026 at 4:00 PM/i })).toBeNull();

    fireEvent.change(screen.getByLabelText("Appointment date"), { target: { value: "2026-07-15" } });
    expect(screen.getByRole("button", { name: /July 15, 2026 at 4:00 PM/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /July 15, 2026 at 9:00 AM/i })).toBeNull();
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

  it("renders configured availability at the slots component position", () => {
    const { container } = render(
      <ReservationBlock
        bookingMode="restricted"
        availableDates={["2026-08-20"]}
        timeSlots={["10:30"]}
        formItems={[
          { id: "instructions", type: "paragraph", text: "Select the best time." },
          { id: "slots", type: "availability", label: "Choose your session" },
          { id: "submit", type: "button", label: "Reserve" },
        ]}
      />
    );

    const customForm = screen.getByTestId("reservation-custom-form");
    expect(screen.queryByRole("heading", { name: "Book an appointment" })).toBeNull();
    expect(container.querySelector(".fixed-slot-contact-grid")).toBeNull();
    expect(container.querySelector(".reservation-block-header")).toBeNull();
    expect(container.querySelector(".reservation-footer")).toBeNull();
    expect(customForm.children[0].textContent).toContain("Select the best time.");
    expect(customForm.children[1].classList.contains("reservation-custom-availability")).toBe(true);
    expect(screen.getByRole("heading", { name: "Choose your session" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /August 20, 2026 at 10:30 AM/i })).toBeTruthy();
    expect(container.querySelectorAll(".fixed-slot-picker")).toHaveLength(1);
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

describe("ReservationBlock custom form", () => {
  it("validates and submits custom text, checkbox, and radio answers", async () => {
    const onSubmit = vi.fn().mockResolvedValue(false);
    render(
      <ReservationBlock
        bookingMode="flexible"
        fields={[]}
        formItems={[
          { id: "intro", type: "heading", text: "Tell us more" },
          { id: "project", type: "text", label: "Project code", required: true },
          { id: "topics", type: "checkbox", label: "Topics", options: ["Design", "Development"], required: true },
          { id: "contact", type: "radio", label: "Preferred contact", options: ["Email", "Phone"], required: true },
          { id: "send", type: "button", label: "Book my session" },
        ]}
        onSubmit={onSubmit}
      />
    );

    expect(screen.getByRole("heading", { name: "Tell us more" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Book my session" }));
    expect(onSubmit).not.toHaveBeenCalled();

    fireEvent.change(screen.getByLabelText(/Project code/), { target: { value: "MADAR-42" } });
    fireEvent.click(screen.getByLabelText("Design"));
    fireEvent.click(screen.getByLabelText("Email"));
    fireEvent.click(screen.getByRole("button", { name: "Book my session" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].customAnswers).toEqual({
      project: "MADAR-42",
      topics: ["Design"],
      contact: "Email",
    });
  });
  it("renders saved typography and RTL direction", () => {
    render(
      <ReservationBlock
        bookingMode="flexible"
        fields={[]}
        formItems={[
          {
            id: "rtl-heading",
            type: "heading",
            text: "احجز موعدك",
            direction: "rtl",
            textStyle: {
              format: "h2",
              fontFamily: "IBM Plex Sans Arabic",
              fontSize: 28,
              opacity: 0.8,
              fontWeight: "700",
              textAlign: "right",
              color: "#123456",
            },
          },
        ]}
      />
    );

    const heading = screen.getByRole("heading", { level: 2, name: "احجز موعدك" });
    expect(heading.getAttribute("dir")).toBe("rtl");
    expect(heading.style.fontSize).toBe("28px");
    expect(heading.style.textAlign).toBe("right");
    expect(heading.style.color).toBe("rgb(18, 52, 86)");
  });
});