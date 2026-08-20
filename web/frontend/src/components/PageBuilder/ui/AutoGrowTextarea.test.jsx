import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import AutoGrowTextarea from "./AutoGrowTextarea";

afterEach(cleanup);

describe("AutoGrowTextarea", () => {
  it("expands to the content scroll height while typing", () => {
    const onChange = vi.fn();
    render(<AutoGrowTextarea aria-label="Description" value="Growing description" onChange={onChange} />);
    const textarea = screen.getByRole("textbox", { name: "Description" });
    Object.defineProperty(textarea, "scrollHeight", { configurable: true, value: 156 });

    fireEvent.input(textarea, { target: { value: "Growing description with more lines" } });

    expect(textarea.style.getPropertyValue("--auto-grow-height")).toBe("156px");
    expect(onChange).toHaveBeenCalled();
  });
});
