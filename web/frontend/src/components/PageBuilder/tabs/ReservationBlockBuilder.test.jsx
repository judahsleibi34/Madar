// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(cleanup);

import { moveBookingComponent } from "../blocks/reservationForm";
import ReservationBlockBuilder from "./ReservationBlockBuilder";

describe("ReservationBlockBuilder", () => {
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

  it("adds from the toolbox, selects the component, and edits it in the inspector", () => {
    const onChange = vi.fn();
    const { rerender } = render(<ReservationBlockBuilder items={[]} onChange={onChange} />);

    expect(screen.getByLabelText("Booking element canvas")).toBeTruthy();
    expect(screen.queryByText("Booking fields")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Heading/ }));

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

    fireEvent.click(screen.getByRole("button", { name: /Available slots/ }));
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
    expect(screen.getByRole("button", { name: /Available slots/ }).disabled).toBe(true);
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
});
