import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, it } from "vitest";
import AgendaDateTimePicker from "./AgendaDateTimePicker";

afterEach(cleanup);
function Fixture() {
  const [value, setValue] = useState("2026-11-13T15:11");
  return <AgendaDateTimePicker value={value} onChange={setValue} />;
}

it("preserves time when choosing a date, supports time editing, and returns focus on Done", () => {
  render(<Fixture />);
  const trigger = screen.getByRole("button", { name: "Choose task date and time" });
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole("button", { name: "Saturday, November 14, 2026" }));
  expect(screen.getByLabelText("Task schedule").value).toBe("2026-11-14T15:11");
  fireEvent.change(screen.getByLabelText("Hour (0–23)"), { target: { value: "10" } });
  fireEvent.change(screen.getByLabelText("Minute"), { target: { value: "30" } });
  expect(screen.getByLabelText("Task schedule").value).toBe("2026-11-14T10:30");
  fireEvent.click(screen.getByRole("button", { name: "Done" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(trigger);
});

it("navigates months, clears the schedule and closes on Escape or outside pointer", () => {
  render(<Fixture />);
  const trigger = screen.getByRole("button", { name: "Choose task date and time" });
  fireEvent.click(trigger);
  fireEvent.click(screen.getByRole("button", { name: "Next month" }));
  expect(screen.getByText("December 2026")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Clear" }));
  expect(screen.getByLabelText("Task schedule").value).toBe("");
  fireEvent.keyDown(document, { key: "Escape" });
  expect(screen.queryByRole("dialog")).toBeNull();
  fireEvent.click(trigger);
  fireEvent.pointerDown(document.body);
  expect(screen.queryByRole("dialog")).toBeNull();
});
