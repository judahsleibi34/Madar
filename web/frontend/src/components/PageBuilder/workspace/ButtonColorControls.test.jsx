import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ButtonColorControls from "./ButtonColorControls";

afterEach(cleanup);

describe("ButtonColorControls", () => {
  it("exposes accessible picker, text, and reset controls for every color", () => {
    const onChange = vi.fn();
    render(<ButtonColorControls element={{ id: "button-1", type: "button" }} onChange={onChange} />);
    [
      "Button background color",
      "Button text color",
      "Button hover background color",
      "Button hover text color",
      "Button border color",
    ].forEach((label) => {
      expect(screen.getByLabelText(label)).toBeTruthy();
      expect(screen.getByLabelText(`${label} picker`)).toBeTruthy();
    });

    fireEvent.change(screen.getByLabelText("Button background color"), { target: { value: "#1a2b3c" } });
    expect(onChange).toHaveBeenCalledWith({ backgroundColor: "#1A2B3C" });
  });

  it("keeps invalid input local and clears a configured color", () => {
    const onChange = vi.fn();
    render(<ButtonColorControls element={{ id: "button-1", type: "button", textColor: "#FFFFFF" }} onChange={onChange} />);
    const input = screen.getByLabelText("Button text color");
    fireEvent.change(input, { target: { value: "url(bad)" } });
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(onChange).not.toHaveBeenCalled();
    fireEvent.click(screen.getAllByRole("button", { name: "Clear" })[1]);
    expect(onChange).toHaveBeenCalledWith({ textColor: "" });
  });

  it("announces non-blocking normal and hover contrast warnings", () => {
    render(<ButtonColorControls element={{
      id: "button-1",
      type: "button",
      textColor: "#777777",
      backgroundColor: "#777777",
      hoverTextColor: "#888888",
      hoverBackgroundColor: "#888888",
    }} onChange={vi.fn()} />);
    expect(screen.getByRole("status").textContent).toContain("Button text contrast may be too low");
    expect(screen.getByRole("status").textContent).toContain("Button hover contrast may be too low");
  });
});
