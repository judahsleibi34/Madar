// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ReservationBlock from "./ReservationBlock";

afterEach(cleanup);

describe("ReservationBlock fixed slots", () => {
  it("translates fixed booking fields, calendar controls and seat labels into Arabic", () => {
    const props = { bookingMode: "restricted", availableDates: ["2026-08-07"], timeSlots: ["09:00"], sessionType: "group", seatCapacity: 3 };
    const { rerender } = render(<ReservationBlock {...props} lang="ar" />);
    expect(screen.getByLabelText("الاسم الكامل *")).toBeTruthy();
    expect(screen.getByLabelText("البريد الإلكتروني *")).toBeTruthy();
    expect(screen.getByLabelText("رقم الهاتف *")).toBeTruthy();
    expect(screen.getByLabelText("عدد المقاعد المطلوبة")).toBeTruthy();
    expect(screen.getByRole("button", { name: "الشهر التالي" })).toBeTruthy();
    expect(screen.getByText("الأوقات المتاحة")).toBeTruthy();
    expect(screen.getByRole("button", { name: /الساعة/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: "إرسال طلب الحجز" })).toBeTruthy();
    rerender(<ReservationBlock {...props} lang="en" />);
    expect(screen.getByLabelText("Full name *")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Next month" })).toBeTruthy();
  });
  it("translates the empty fixed-slot state", () => {
    render(<ReservationBlock lang="ar" bookingMode="restricted" availableDates={[]} />);
    expect(screen.getByText("لا توجد مواعيد متاحة حاليًا.")).toBeTruthy();
  });
  it("submits a group seat quantity and validates the seat limit", async () => {
    const submit = vi.fn().mockResolvedValue(false);
    const { container } = render(<ReservationBlock bookingMode="restricted"
      availableDates={["2026-08-07"]} timeSlotsByDate={{ "2026-08-07": ["09:00", "11:00"] }}
      sessionSettingsByDate={{ "2026-08-07": { "09:00": { sessionType: "group", seatCapacity: 3 } } }}
      formItems={[{ id: "availability", type: "availability", label: "Pick a session" }, { id: "send", type: "button", label: "Reserve seats" }]}
      onSubmit={submit} submitLabel="Reserve seats" />);
    fireEvent.click(screen.getByRole("button", { name: /August 7, 2026 at 9:00 AM/ }));
    fireEvent.change(screen.getByLabelText("Seats to book"), { target: { value: "4" } });
    fireEvent.submit(container.querySelector("form"));
    expect(submit).not.toHaveBeenCalled();
    expect(screen.getByRole("alert").textContent).toBe("Choose between 1 and 3 seats.");
    fireEvent.change(screen.getByLabelText("Seats to book"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Reserve seats" }));
    await waitFor(() => expect(submit).toHaveBeenCalled());
    expect(submit.mock.calls[0][0].guests).toBe(2);
    fireEvent.click(screen.getByRole("button", { name: /August 7, 2026 at 11:00 AM/ }));
    expect(screen.queryByLabelText("Seats to book")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Reserve seats" }));
    await waitFor(() => expect(submit).toHaveBeenCalledTimes(2));
    expect(submit.mock.calls[1][0].guests).toBe(1);
  });

  it("offers weekly dates in later months and removes them when repetition is disabled", () => {
    const props = {
      bookingMode: "restricted", availableDates: ["2026-08-07"],
      timeSlotsByDate: { "2026-08-07": ["09:00"] }, weeklyRepeatDates: ["2026-08-07"],
    };
    const { rerender } = render(<ReservationBlock {...props} />);
    fireEvent.click(screen.getByRole("button", { name: "Next month" }));
    const date = screen.getByRole("button", { name: "Friday, September 4, 2026, available" });
    expect(date.disabled).toBe(false);
    fireEvent.click(date);
    expect(screen.getByRole("button", { name: /September 4, 2026 at 9:00 AM/i })).toBeTruthy();
    rerender(<ReservationBlock {...props} weeklyRepeatDates={[]} />);
    expect(screen.getByRole("button", { name: "Friday, September 4, 2026, unavailable" }).disabled).toBe(true);
  });

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

    expect(screen.getByRole("button", { name: /Tuesday, July 14, 2026, available/i }).getAttribute("aria-pressed")).toBe("true");
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

    fireEvent.click(screen.getByRole("button", { name: /Wednesday, July 15, 2026, available/i }));
    expect(screen.getByRole("button", { name: /July 15, 2026 at 4:00 PM/i })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /July 15, 2026 at 9:00 AM/i })).toBeNull();
  });
  it("navigates months and exposes only configured dates as available", () => {
    render(
      <ReservationBlock
        bookingMode="restricted"
        availableDates={["2026-07-31", "2026-08-03"]}
        timeSlots={["09:00"]}
      />
    );

    expect(screen.getByText("July 2026")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Friday, July 31, 2026, available/i }).disabled).toBe(false);
    expect(screen.getByRole("button", { name: /Thursday, July 30, 2026, unavailable/i }).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Next month" }));
    expect(screen.getByText("August 2026")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Monday, August 3, 2026, available/i }).disabled).toBe(false);
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

    await waitFor(() => expect(screen.getByRole("button", { name: /Monday, July 20, 2026, available/i })).toBeTruthy());
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

  it("applies the saved direction to every part of the availability component", () => {
    const { container } = render(
      <ReservationBlock
        bookingMode="restricted"
        availableDates={["2026-08-20"]}
        timeSlots={["10:30"]}
        formItems={[{ id: "slots", type: "availability", label: "Choose your session", direction: "rtl" }]}
      />
    );

    expect(container.querySelector(".reservation-custom-availability").getAttribute("dir")).toBe("rtl");
    expect(container.querySelector(".fixed-slot-picker").getAttribute("dir")).toBe("rtl");
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
  it("translates the starter text inside an existing saved form in Arabic", () => {
    const formItems = [
      { id: "intro", type: "heading", text: "Reserve now", translations: { ar: { text: "احجز الآن" } } },
      { id: "help", type: "paragraph", text: "Choose the service, date, and time that works for you." },
      { id: "email", type: "email", label: "Email address", placeholder: "you@example.com" },
      { id: "new", type: "heading", text: "New section heading" },
      { id: "question", type: "text", label: "Your question", placeholder: "Type your answer" },
      { id: "send", type: "button", label: "Send request" },
    ];
    const { rerender } = render(<ReservationBlock lang="ar" formItems={JSON.parse(JSON.stringify(formItems))} />);
    expect(screen.getByRole("heading", { name: "احجز الآن" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "عنوان جديد" })).toBeTruthy();
    expect(screen.getByText("اختر الخدمة والتاريخ والوقت المناسب لك.")).toBeTruthy();
    expect(screen.getByLabelText("البريد الإلكتروني")).toBeTruthy();
    expect(screen.getByPlaceholderText("اكتب إجابتك")).toBeTruthy();
    expect(screen.getByRole("button", { name: "إرسال الطلب" })).toBeTruthy();
    rerender(<ReservationBlock lang="en" formItems={formItems} />);
    expect(screen.getByLabelText("Your question")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send request" })).toBeTruthy();
  });
  it("preserves the default service value in Arabic submissions", async () => {
    const submit = vi.fn().mockResolvedValue(false);
    render(<ReservationBlock lang="ar" fields={["service"]} onSubmit={submit} />);
    fireEvent.click(screen.getByRole("button", { name: "إرسال طلب الحجز" }));
    await waitFor(() => expect(submit).toHaveBeenCalled());
    expect(submit.mock.calls[0][0].service).toBe("Consultation");
  });
  it("sets Arabic form flow and mirrors untranslated question controls", () => {
    const { container, rerender } = render(<ReservationBlock lang="ar" formItems={[
      { id: "name", type: "text", label: "Name", direction: "ltr" },
      { id: "choice", type: "radio", label: "Choice", options: ["One"] },
    ]} />);
    expect(container.querySelector('form').dir).toBe("rtl");
    expect(container.querySelector('.reservation-custom-form').dir).toBe("rtl");
    expect(screen.getByLabelText("Name").dir).toBe("rtl");
    expect(screen.getByRole("group", { name: "Choice" }).dir).toBe("rtl");
    rerender(<ReservationBlock lang="en" formItems={[{ id: "name", type: "text", label: "Name", direction: "ltr" }]} />);
    expect(container.querySelector('.reservation-custom-form').dir).toBe("ltr");
  });
  it("renders a saved divider between authored components", () => {
    const { container } = render(<ReservationBlock formItems={[
      { id: "intro", type: "heading", text: "Book a visit" },
      { id: "line", type: "divider", layout: { desktop: { columns: 6, position: "center" } } },
      { id: "send", type: "button", label: "Send request" },
    ]} />);
    const divider = screen.getByRole("separator");
    expect(divider.getAttribute("aria-orientation")).toBe("horizontal");
    expect(divider.style.getPropertyValue("--booking-desktop-span")).toBe("6");
    expect(container.querySelector('.reservation-custom-form').children[1]).toBe(divider);
  });
  it("shows translated content but submits original choice values", async () => {
    const onSubmit = vi.fn().mockResolvedValue(false);
    render(<ReservationBlock lang="ar" bookingMode="flexible" fields={[]} onSubmit={onSubmit}
      formItems={[
        { id: "intro", type: "heading", text: "Book", translations: { ar: { text: "احجز موعدك" } } },
        { id: "note", type: "text", label: "Note", translations: { ar: { label: "ملاحظة", placeholder: "اكتب هنا" } } },
        { id: "time", type: "radio", label: "Time", required: true, options: ["Morning", "Evening"],
          translations: { ar: { label: "الوقت", options: { Morning: "صباحًا", Evening: "مساءً" } } } },
        { id: "send", type: "button", label: "Send", translations: { ar: { label: "إرسال" } } },
      ]} />);
    expect(screen.getByRole("heading", { name: "احجز موعدك" })).toBeTruthy();
    expect(screen.getByPlaceholderText("اكتب هنا")).toBeTruthy();
    fireEvent.click(screen.getByLabelText("صباحًا"));
    fireEvent.click(screen.getByRole("button", { name: "إرسال" }));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].customAnswers.time).toBe("Morning");
  });
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
  it("validates dedicated email and regional phone components before submitting", async () => {
    const onSubmit = vi.fn().mockResolvedValue(false);
    render(
      <ReservationBlock
        bookingMode="flexible"
        fields={[]}
        formItems={[
          { id: "email", type: "email", label: "Email address", required: true },
          { id: "phone", type: "phone", label: "Phone number", required: true },
          { id: "send", type: "button", label: "Book now" },
        ]}
        onSubmit={onSubmit}
      />
    );

    fireEvent.change(screen.getByLabelText(/Email address/), { target: { value: "invalid" } });
    fireEvent.change(screen.getByLabelText(/Phone number/), { target: { value: "+971 50 123 4567" } });
    fireEvent.click(screen.getByRole("button", { name: "Book now" }));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText(/valid email address/)).toBeTruthy();
    expect(screen.getByText(/Palestinian \(\+970\).*Israeli \(\+972\)/)).toBeTruthy();

    fireEvent.change(screen.getByLabelText(/Email address/), { target: { value: "person@example.com" } });
    fireEvent.change(screen.getByLabelText(/Phone number/), { target: { value: "+970 59 123 4567" } });
    fireEvent.click(screen.getByRole("button", { name: "Book now" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].customAnswers).toEqual({
      email: "person@example.com",
      phone: "+970 59 123 4567",
    });
  });
});
