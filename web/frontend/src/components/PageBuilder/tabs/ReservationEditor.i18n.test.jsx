// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import i18n from "../../../i18n";
import "../../../i18n/allTranslations";
import en from "../../../i18n/locales/en/pageBuilder.json";
import ar from "../../../i18n/locales/ar/pageBuilder.json";
import ReservationBlockBuilder from "./ReservationBlockBuilder";
import ReservationsTab from "./ReservationsTab";

afterEach(async () => { cleanup(); await i18n.changeLanguage("en"); });

describe("booking editor translations", () => {
  it("provides an Arabic back button from the form editor to reservations", async () => {
    await i18n.changeLanguage("ar");
    const { container } = render(<ReservationsTab reservationBlocks={[{ page: { id: "page" }, element: {
      id: "book", name: "Booking", reservation: { bookingMode: "flexible", formItems: [] },
    } }]} activeReservationId="book" onAddReservationBlock={vi.fn()} onSelectReservationBlock={vi.fn()}
      onUpdateReservationBlock={vi.fn()} onDeleteReservationBlock={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "العودة إلى الحجوزات" }));
    expect(container.querySelector('.is-form-editing')).toBeNull();
    expect(screen.getByRole("heading", { name: "الحجوزات", exact: true })).toBeTruthy();
  });
  it("shows the automatic starter translation inside the Arabic editing field", async () => {
    await i18n.changeLanguage("en");
    const change = vi.fn();
    render(<ReservationBlockBuilder items={[{ id: "new", type: "heading", text: "New section heading" }]} onChange={change} />);
    fireEvent.change(screen.getByLabelText("Preview language"), { target: { value: "ar" } });
    expect(screen.getByRole("heading", { name: "عنوان جديد" })).toBeTruthy();
    expect(screen.getByLabelText("العربية Text").value).toBe("عنوان جديد");
    fireEvent.change(screen.getByLabelText("العربية Text"), { target: { value: "عنواني" } });
    expect(change.mock.calls.at(-1)[0][0].translations.ar.text).toBe("عنواني");
    expect(change.mock.calls.at(-1)[0][0].text).toBe("New section heading");
  });
  it("mirrors Arabic preview and honors per-language direction toggles without rewriting English text", async () => {
    await i18n.changeLanguage("en");
    const change = vi.fn();
    const original = [{ id: "intro", type: "heading", text: "Reserve now", direction: "ltr" }];
    const { container, rerender } = render(<ReservationBlockBuilder items={original} onChange={change} />);
    fireEvent.change(screen.getByLabelText("Preview language"), { target: { value: "ar" } });
    expect(container.querySelector('.booking-form-page').dir).toBe("rtl");
    expect(container.querySelector('article').dir).toBe("rtl");
    fireEvent.click(screen.getByRole("button", { name: "LTR", exact: true }));
    const saved = change.mock.calls.at(-1)[0];
    expect(saved[0].translations.ar.direction).toBe("ltr");
    expect(saved[0].text).toBe("Reserve now");
    expect(saved[0].direction).toBe("ltr");
    rerender(<ReservationBlockBuilder items={saved} onChange={change} />);
    expect(container.querySelector('article').dir).toBe("ltr");
    fireEvent.change(screen.getByLabelText("Preview language"), { target: { value: "en" } });
    fireEvent.click(screen.getByRole("button", { name: "RTL", exact: true }));
    rerender(<ReservationBlockBuilder items={change.mock.calls.at(-1)[0]} onChange={change} />);
    expect(container.querySelector('article').dir).toBe("rtl");
    expect(container.querySelector('.booking-form-page').dir).toBe("ltr");
  });
  it("loads English heading text and keeps the heading, translation and canvas synchronized", async () => {
    await i18n.changeLanguage("en");
    const change = vi.fn();
    const items = [{ id: "intro", type: "heading", text: "Reserve now", translations: { en: { text: "Old heading" }, ar: { text: "احجز الآن" } } }];
    const { rerender } = render(<ReservationBlockBuilder items={items} onChange={change} />);
    expect(screen.getByLabelText("English Text").value).toBe("Reserve now");
    expect(screen.getByRole("heading", { name: "Reserve now" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Heading text"), { target: { value: "Book a visit" } });
    const updated = change.mock.calls.at(-1)[0];
    expect(updated[0].translations.en.text).toBe("Book a visit");
    expect(updated[0].translations.ar.text).toBe("احجز الآن");
    rerender(<ReservationBlockBuilder items={updated} onChange={change} />);
    expect(screen.getByLabelText("English Text").value).toBe("Book a visit");
    fireEvent.change(screen.getByLabelText("English Text"), { target: { value: "Choose your session" } });
    const english = change.mock.calls.at(-1)[0];
    expect(english[0].text).toBe("Choose your session");
    expect(english[0].translations.en.text).toBe("Choose your session");
    rerender(<ReservationBlockBuilder items={english} onChange={change} />);
    expect(screen.getByLabelText("Heading text").value).toBe("Choose your session");
  });
  it("edits authored translations separately and previews the selected content language", async () => {
    await i18n.changeLanguage("en");
    const change = vi.fn();
    const items = [{ id: "intro", type: "heading", text: "Book your visit" }];
    const { rerender } = render(<ReservationBlockBuilder items={items} onChange={change} />);
    const translations = screen.getByRole("region", { name: "Translations" });
    const inspector = screen.getByRole("complementary", { name: "Selected booking component settings" });
    expect(translations.tagName).toBe("SECTION");
    expect(inspector.querySelector(".booking-component-direction").compareDocumentPosition(translations) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
    expect(screen.getByRole("group", { name: "Component content direction" })).toBeTruthy();
    expect(screen.getByRole("toolbar", { name: "Booking text formatting" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "العربية" }));
    fireEvent.change(screen.getByLabelText("العربية Text"), { target: { value: "احجز زيارتك" } });
    const saved = JSON.parse(JSON.stringify(change.mock.calls.at(-1)[0]));
    expect(saved[0].text).toBe("Book your visit");
    expect(saved[0].translations.ar.text).toBe("احجز زيارتك");
    rerender(<ReservationBlockBuilder items={saved} onChange={change} />);
    expect(screen.getByRole("heading", { name: "احجز زيارتك" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Preview language"), { target: { value: "en" } });
    expect(screen.getByRole("heading", { name: "Book your visit" })).toBeTruthy();
  });
  it("provides Arabic for every English editor message", () => {
    const visit = (english, arabic) => {
      expect(Object.keys(arabic).sort()).toEqual(Object.keys(english).sort());
      for (const [key, value] of Object.entries(english)) {
        if (typeof value === "object") visit(value, arabic[key]);
        else { expect(typeof arabic[key]).toBe("string"); expect(arabic[key]).not.toBe(value); }
      }
    };
    visit(en.bookingEditor, ar.bookingEditor);
  });

  it("switches editor chrome to Arabic without rewriting authored text", async () => {
    await i18n.changeLanguage("ar");
    const change = vi.fn();
    const item = { id: "intro", type: "heading", text: "Keep my wording", direction: "ltr" };
    const { container } = render(<ReservationBlockBuilder items={[item]} onChange={change} />);
    expect(container.querySelector(".booking-element-builder").dir).toBe("rtl");
    expect(screen.getByRole("heading", { name: "إضافة حقول" })).toBeTruthy();
    expect(screen.getByText("Keep my wording")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /^البريد الإلكتروني/ }));
    expect(change.mock.calls.at(-1)[0][0]).toEqual(item);
    expect(change.mock.calls.at(-1)[0][1]).toEqual(expect.objectContaining({ label: "البريد الإلكتروني", direction: "rtl" }));
    fireEvent.click(screen.getByRole("button", { name: /^عنوان/ }));
    expect(change.mock.calls.at(-1)[0][1]).toEqual(expect.objectContaining({ text: "عنوان جديد", direction: "rtl",
      textStyle: expect.objectContaining({ fontFamily: "IBM Plex Sans Arabic", textAlign: "right" }) }));
  });

  it("localizes the date picker and appointment controls", async () => {
    await i18n.changeLanguage("ar");
    const { container } = render(<ReservationsTab reservationBlocks={[{
      page: { id: "page", name: "Customer page" }, element: { id: "book", name: "Customer form", reservation: {
        bookingMode: "restricted", availableDates: ["2026-08-07"], timeSlotsByDate: { "2026-08-07": ["09:00"] },
      } },
    }]} activeReservationId="book" onAddReservationBlock={vi.fn()} onSelectReservationBlock={vi.fn()}
      onUpdateReservationBlock={vi.fn()} onDeleteReservationBlock={vi.fn()} />);
    expect(container.querySelector("main").dir).toBe("rtl");
    expect(screen.getByRole("button", { name: "إضافة وقت" })).toBeTruthy();
    expect(screen.getByRole("checkbox", { name: "تكرار أسبوعي" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /اختر تاريخًا/ }));
    expect(screen.getByRole("dialog", { name: "اختر تاريخًا متاحًا" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "الشهر التالي" })).toBeTruthy();
  });
});
