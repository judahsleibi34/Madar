import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useRef, useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import DateTimeInput from "./DateTimeInput";
let locale = "en";
vi.mock("react-i18next", () => ({ useTranslation: () => ({ i18n: { get resolvedLanguage() { return locale; } } }) }));
afterEach(() => { cleanup(); locale = "en"; });
function Fixture({ type = "date", initial = "2026-11-13", ...props }) {
  const [value, setValue] = useState(initial);
  return <form><label>Field<DateTimeInput name="schedule" aria-label="Field" type={type} value={value} onChange={(event) => setValue(event.target.value)} {...props} /></label></form>;
}
it("honors date bounds and keeps native form serialization and required validation", () => {
  render(<Fixture min="2026-11-12" max="2026-11-14" required />);
  fireEvent.click(screen.getByRole("button", { name: "Choose date" }));
  expect(screen.getByRole("button", { name: "Wednesday, November 11, 2026" }).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Saturday, November 14, 2026" }));
  const field = screen.getByLabelText("Field");
  expect(field.value).toBe("2026-11-14");
  expect(new FormData(field.form).get("schedule")).toBe("2026-11-14");
  expect(document.querySelector("label label")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Clear" }));
  expect(field.validity.valueMissing).toBe(true);
});
it("edits a time-only field and preserves direct typing", () => {
  render(<Fixture type="time" initial="15:11" />);
  fireEvent.click(screen.getByRole("button", { name: "Choose time" }));
  expect(screen.queryByRole("button", { name: "Next month" })).toBeNull();
  fireEvent.change(screen.getByLabelText("Hour (0–23)"), { target: { value: "10" } });
  fireEvent.change(screen.getByLabelText("Minute"), { target: { value: "30" } });
  expect(screen.getByLabelText("Field").value).toBe("10:30");
  fireEvent.change(screen.getByLabelText("Field"), { target: { value: "16:45" } });
  expect(screen.getByLabelText("Field").value).toBe("16:45");
});
it("clamps a combined selection to the time allowed on the boundary date", () => {
  render(<Fixture type="datetime-local" initial="2026-11-13T09:00" min="2026-11-12T15:00" />);
  fireEvent.click(screen.getByRole("button", { name: "Choose date and time" }));
  fireEvent.click(screen.getByRole("button", { name: "Thursday, November 12, 2026" }));
  expect(screen.getByLabelText("Field").value).toBe("2026-11-12T15:00");
});
it("supports uncontrolled input and forwarded refs without changing normal text inputs", () => {
  function Uncontrolled() {
    const ref = useRef(null);
    return <><DateTimeInput type="date" aria-label="Uncontrolled" defaultValue="2026-11-13" ref={ref} /><button onClick={() => ref.current.focus()}>Focus field</button><DateTimeInput type="text" aria-label="Plain text" defaultValue="Text" /></>;
  }
  render(<Uncontrolled />);
  fireEvent.click(screen.getByRole("button", { name: "Choose date" }));
  fireEvent.click(screen.getByRole("button", { name: "Saturday, November 14, 2026" }));
  expect(screen.getByLabelText("Uncontrolled").value).toBe("2026-11-14");
  fireEvent.click(screen.getByRole("button", { name: "Focus field" }));
  expect(document.activeElement).toBe(screen.getByLabelText("Uncontrolled"));
  expect(screen.getByLabelText("Plain text").closest(".madar-date-input")).toBeNull();
});
it("does not open disabled, readonly or disabled-fieldset controls", () => {
  render(<><DateTimeInput type="date" disabled /><DateTimeInput type="date" readOnly /><fieldset disabled><DateTimeInput type="date" /></fieldset></>);
  for (const button of screen.getAllByRole("button", { name: "Choose date" })) fireEvent.click(button);
  expect(screen.queryByRole("dialog")).toBeNull();
});
it("renders the shared picker in Arabic with RTL direction", () => {
  locale = "ar";
  render(<Fixture />);
  fireEvent.click(screen.getByRole("button", { name: "اختر التاريخ" }));
  expect(screen.getByRole("dialog").getAttribute("dir")).toBe("rtl");
  expect(screen.getByRole("button", { name: "تم" })).toBeTruthy();
});
