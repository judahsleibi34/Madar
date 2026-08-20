import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PageBuilderIconPicker, { builderIconOptions } from "./PageBuilderIconPicker";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("PageBuilderIconPicker", () => {
  it("keeps the growing icon library collapsed until requested", () => {
    render(<PageBuilderIconPicker value="Sparkles" onChange={vi.fn()} />);

    expect(screen.queryByRole("searchbox")).toBeNull();
    expect(screen.queryByRole("button", { name: "Camera" })).toBeNull();
    const toggle = screen.getByRole("button", { name: `Show all ${builderIconOptions.length} icons` });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");

    fireEvent.click(toggle);
    expect(screen.getByRole("button", { name: "Christian cross" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Wedding rings" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Collapse icons" }).getAttribute("aria-expanded")).toBe("true");
  });

  it("starts expanded when the saved icon is outside the compact set", () => {
    render(<PageBuilderIconPicker value="Camera" onChange={vi.fn()} />);

    expect(screen.getByRole("button", { name: "Camera" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Collapse icons" })).toBeTruthy();
  });

  it("groups the full icon library when expanded", () => {
    render(<PageBuilderIconPicker value="Sparkles" onChange={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: `Show all ${builderIconOptions.length} icons` }));

    expect(screen.getByRole("region", { name: "Wedding & celebration" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Wedding rings" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Camera" })).toBeTruthy();
  });

  it("offers a family and people category", () => {
    render(<PageBuilderIconPicker value="Sparkles" onChange={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: `Show all ${builderIconOptions.length} icons` }));

    expect(screen.getByRole("region", { name: "Family & people" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Family" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Family home" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Family care" })).toBeTruthy();
  });
});
