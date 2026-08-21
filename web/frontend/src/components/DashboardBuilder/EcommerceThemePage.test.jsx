import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EcommerceThemePage from "./EcommerceThemePage";
import { fetchEcommerceTheme, saveEcommerceTheme } from "../../services/ecommerceApi";

vi.mock("../../services/ecommerceApi", () => ({
  fetchEcommerceTheme: vi.fn(),
  saveEcommerceTheme: vi.fn(),
}));

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
  fetchEcommerceTheme.mockResolvedValue({
    theme: {
      accent: "#2463eb",
      background: "#ffffff",
      surface: "#f7f8fa",
      text: "#151821",
      muted: "#697181",
    },
  });
  saveEcommerceTheme.mockImplementation(async (theme) => ({ theme }));
});

describe("EcommerceThemePage", () => {
  it("loads, previews, and saves storefront colors", async () => {
    render(<EcommerceThemePage />);

    expect(await screen.findByLabelText("Store colors")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Main color"), { target: { value: "#a33a2b" } });
    expect(screen.getByLabelText("Main color").value).toBe("#a33a2b");
    fireEvent.click(screen.getByRole("button", { name: "Save colors" }));

    await waitFor(() => expect(saveEcommerceTheme).toHaveBeenCalledWith(expect.objectContaining({ accent: "#a33a2b" }), { scope: "authenticated" }));
    expect(await screen.findByText("Store colors saved")).toBeTruthy();
  });

  it("rejects incomplete color values with a toast", async () => {
    render(<EcommerceThemePage />);
    await screen.findByLabelText("Store colors");

    fireEvent.change(screen.getByLabelText("Main color"), { target: { value: "#123" } });
    fireEvent.click(screen.getByRole("button", { name: "Save colors" }));

    expect(await screen.findByText("Check the colors")).toBeTruthy();
    expect(saveEcommerceTheme).not.toHaveBeenCalled();
  });
});
