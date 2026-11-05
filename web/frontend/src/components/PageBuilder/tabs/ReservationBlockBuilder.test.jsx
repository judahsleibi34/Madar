// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

import { moveBookingComponent } from "../blocks/reservationForm";
import ReservationBlockBuilder from "./ReservationBlockBuilder";

describe("ReservationBlockBuilder", () => {
  it("resizes a submit button vertically with its corner handle", () => {
    const change = vi.fn();
    render(<ReservationBlockBuilder items={[{ id: "send", type: "button", label: "Send" }]} onChange={change} />);
    fireEvent.keyDown(screen.getByRole("button", { name: /Resize component/ }), { key: "ArrowDown" });
    expect(change.mock.calls.at(-1)[0][0].layout.desktop).toMatchObject({ columns: 12, contentHeight: 44 });
    expect(change.mock.calls.at(-1)[0][0].layout.mobile).toBeUndefined();
  });
  it("adds a movable divider without text settings and can remove it", () => {
    const change = vi.fn();
    const { rerender } = render(<ReservationBlockBuilder items={[]} onChange={change} />);
    fireEvent.click(screen.getByRole("button", { name: /^Divider/ }));
    const added = change.mock.calls.at(-1)[0];
    expect(added[0].type).toBe("divider");
    rerender(<ReservationBlockBuilder items={added} onChange={change} />);
    expect(screen.getByRole("separator").getAttribute("aria-orientation")).toBe("horizontal");
    expect(screen.getByRole("button", { name: /Move component/ })).toBeTruthy();
    expect(screen.queryByText("Translations")).toBeNull();
    expect(screen.queryByLabelText("Question label")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Remove field" }));
    expect(change.mock.calls.at(-1)[0]).toEqual([]);
  });
  it("moves a full-width component below another heading and back without adding spacing or changing its data", () => {
    const change = vi.fn();
    const item = { id: "intro", type: "heading", text: "Book", translations: { ar: { text: "احجز" } }, layout: { mobile: { columns: 6 } } };
    const second = { id: "new", type: "heading", text: "New header" };
    const { rerender } = render(<ReservationBlockBuilder items={[item, second]} onChange={change} />);
    fireEvent.keyDown(screen.getAllByRole("article", { name: "Heading component" })[0].querySelector(".direct-move-handle"), { key: "ArrowDown" });
    const down = change.mock.calls.at(-1)[0];
    expect(down).toEqual([second, item]);
    rerender(<ReservationBlockBuilder items={down} onChange={change} />);
    fireEvent.keyDown(screen.getAllByRole("article", { name: "Heading component" })[1].querySelector(".direct-move-handle"), { key: "ArrowUp" });
    expect(change.mock.calls.at(-1)[0]).toEqual([item, second]);
  });
  it("moves components horizontally without cloning them or changing another device", () => {
    const change = vi.fn();
    const item = { id: "heading", type: "heading", text: "Book", layout: { desktop: { columns: 6 }, mobile: { columns: 12 } } };
    const { rerender } = render(<ReservationBlockBuilder items={[item]} onChange={change} />);
    fireEvent.keyDown(screen.getByRole("button", { name: /Move component/ }), { key: "ArrowRight" });
    const moved = change.mock.calls.at(-1)[0];
    expect(moved).toHaveLength(1);
    expect(moved[0].id).toBe(item.id);
    expect(moved[0].layout.desktop).toMatchObject({ columns: 6, position: "custom", startColumn: 2 });
    expect(moved[0].layout.mobile.columns).toBe(12);
    rerender(<ReservationBlockBuilder items={moved} onChange={change} />);
    fireEvent.keyDown(screen.getByRole("button", { name: /Move component/ }), { key: "ArrowRight" });
    expect(change.mock.calls.at(-1)[0][0].layout.desktop.startColumn).toBe(3);
    fireEvent.click(screen.getByRole("button", { name: "Mobile", exact: true }));
    expect(screen.getByRole("button", { name: /Move component/ }).disabled).toBe(false);
  });
  it("resizes independent device layouts directly without a size settings panel", () => {
    const change = vi.fn();
    const item = { id: "heading", type: "heading", text: "Book", translations: { ar: { text: "احجز" } } };
    const { rerender } = render(<ReservationBlockBuilder items={[item]} onChange={change} />);
    expect(screen.queryByRole("region", { name: "Size and position" })).toBeNull();
    fireEvent.keyDown(screen.getByRole("button", { name: /Resize component/ }), { key: "ArrowLeft" });
    const desktop = change.mock.calls.at(-1)[0];
    expect(desktop[0].layout.desktop.columns).toBe(11);
    expect(desktop[0].translations).toEqual(item.translations);
    rerender(<ReservationBlockBuilder items={desktop} onChange={change} />);
    fireEvent.click(screen.getByRole("button", { name: "Mobile", exact: true }));
    expect(screen.getByRole("button", { name: /Move component/ }).disabled).toBe(false);
    fireEvent.keyDown(screen.getByRole("button", { name: /Resize component/ }), { key: "ArrowLeft" });
    const mobile = change.mock.calls.at(-1)[0];
    expect(mobile[0].layout.mobile.columns).toBe(11);
    expect(mobile[0].layout.desktop.columns).toBe(11);
    rerender(<ReservationBlockBuilder items={mobile} onChange={change} />);
    fireEvent.click(screen.getByRole("button", { name: "Desktop", exact: true }));
    expect(screen.getByRole("button", { name: /Move component/ }).disabled).toBe(false);
  });

  it("edits canvas text directly without changing another field or its translations", () => {
    const change = vi.fn();
    const items = [{ id: "heading", type: "heading", text: "Book", translations: { ar: { text: "احجز" } } },
      { id: "paragraph", type: "paragraph", text: "Welcome" }];
    const { rerender } = render(<ReservationBlockBuilder items={items} onChange={change} />);
    const heading = screen.getByRole("heading", { name: "Book" });
    expect(heading.getAttribute("contenteditable")).toBe("plaintext-only");
    fireEvent.click(heading);
    heading.textContent = "Book your session";
    fireEvent.blur(heading);
    const saved = change.mock.calls.at(-1)[0];
    expect(saved[0]).toEqual({ ...items[0], text: "Book your session", translations: { ...items[0].translations, en: { text: "Book your session" } } });
    expect(saved[1]).toEqual(items[1]);
    rerender(<ReservationBlockBuilder items={saved} onChange={change} />);
    fireEvent.change(screen.getByLabelText("Preview language"), { target: { value: "ar" } });
    const translated = screen.getByRole("heading", { name: "احجز" });
    translated.textContent = "احجز جلستك";
    fireEvent.blur(translated);
    expect(change.mock.calls.at(-1)[0][0]).toEqual({ ...saved[0], translations: { ...saved[0].translations, ar: { text: "احجز جلستك" } } });
  });

  it("moves booking components by their saved ids", () => {
    const items = [
      { id: "heading", type: "heading", text: "Book" },
      { id: "question", type: "text", label: "Name" },
      { id: "submit", type: "button", label: "Reserve" },
    ];

    expect(moveBookingComponent(items, "submit", 0).map((item) => item.id)).toEqual([
      "submit", "heading", "question",
    ]);
    expect(moveBookingComponent(items, "heading", 3).map((item) => item.id)).toEqual([
      "question", "submit", "heading",
    ]);
  });

  it("has no order tab and still reorders fields directly on the canvas", () => {
    const change = vi.fn();
    const items = [{ id: "heading", type: "heading", text: "Book" },
      { id: "name", type: "text", label: "Your name", required: true },
      { id: "send", type: "button", label: "Send" }];
    const { rerender } = render(<ReservationBlockBuilder items={items} onChange={change} />);
    expect(screen.queryByRole("tab", { name: "Field order" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Add fields" })).toBeTruthy();
    fireEvent.keyDown(screen.getByRole("article", { name: "Submit button component" }).querySelector('.direct-move-handle'), { key: "ArrowUp" });
    const reordered = change.mock.calls.at(-1)[0];
    expect(reordered.map(item => item.id)).toEqual(["heading", "send", "name"]);
    expect(reordered[2]).toEqual(items[1]);
    rerender(<ReservationBlockBuilder items={reordered} onChange={change} />);
    fireEvent.keyDown(screen.getByRole("article", { name: "Submit button component" }), { key: "ArrowUp", altKey: true });
    expect(change.mock.calls.at(-1)[0].map(item => item.id)).toEqual(["send", "heading", "name"]);
  });

  it("adds from the toolbox, selects the component, and edits it in the inspector", () => {
    const onChange = vi.fn();
    const { rerender } = render(<ReservationBlockBuilder items={[]} onChange={onChange} />);

    expect(screen.getByLabelText("Booking element canvas")).toBeTruthy();
    expect(screen.queryByText("Booking fields")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /^Heading/ }));

    const addedItems = onChange.mock.calls.at(-1)[0];
    expect(addedItems[0]).toEqual(expect.objectContaining({ type: "heading" }));

    rerender(<ReservationBlockBuilder items={addedItems} onChange={onChange} />);
    expect(screen.getByLabelText("Selected booking component settings")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Heading text"), { target: { value: "Choose your appointment" } });

    expect(onChange.mock.calls.at(-1)[0][0].text).toBe("Choose your appointment");
  });
  it("adds one slots component backed by configured availability", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <ReservationBlockBuilder
        items={[]}
        availableDates={["2026-08-20"]}
        timeSlots={["09:00", "10:30"]}
        allowAvailability
        onChange={onChange}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /^Available slots/ }));
    const addedItems = onChange.mock.calls.at(-1)[0];
    expect(addedItems[0]).toEqual(expect.objectContaining({
      type: "availability",
      label: "Choose an available slot",
    }));

    rerender(
      <ReservationBlockBuilder
        items={addedItems}
        availableDates={["2026-08-20"]}
        timeSlots={["09:00", "10:30"]}
        allowAvailability
        onChange={onChange}
      />
    );

    expect(screen.getByText("2026-08-20")).toBeTruthy();
    expect(screen.getByText("09:00")).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Available slots/ }).disabled).toBe(true);
  });
  it("saves typography and direction controls for the selected component", () => {
    const onChange = vi.fn();
    const items = [{
      id: "intro",
      type: "paragraph",
      text: "Welcome",
      direction: "ltr",
      textStyle: { format: "text", fontFamily: "Inter", fontSize: 16 },
    }];
    const { rerender } = render(<ReservationBlockBuilder items={items} onChange={onChange} />);

    expect(screen.getByRole("toolbar", { name: "Booking text formatting" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Bold" }));
    const boldItems = onChange.mock.calls.at(-1)[0];
    expect(boldItems[0].textStyle.fontWeight).toBe("700");

    rerender(<ReservationBlockBuilder items={boldItems} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "RTL" }));
    expect(onChange.mock.calls.at(-1)[0][0]).toEqual(expect.objectContaining({
      direction: "rtl",
      textStyle: expect.objectContaining({ textAlign: "right" }),
    }));
  });
  it("offers dedicated draggable Email and Phone components", () => {
    const onChange = vi.fn();
    render(<ReservationBlockBuilder items={[]} onChange={onChange} />);

    expect(screen.getByRole("button", { name: /^Email/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /^Phone number/ })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /^Email/ }));
    expect(onChange.mock.calls.at(-1)[0][0]).toEqual(expect.objectContaining({
      type: "email",
      label: "Email address",
      required: true,
    }));
  });
});
