import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EcommerceThemePage from "./EcommerceThemePage";
import { fetchEcommerceTheme, saveEcommerceTheme } from "../../services/ecommerceApi";
import { fetchWebsiteSettings } from "../PageBuilder/services/PageBuilder.api";

vi.mock("../../services/ecommerceApi", () => ({
  fetchEcommerceTheme: vi.fn(),
  saveEcommerceTheme: vi.fn(),
}));

vi.mock("../PageBuilder/services/PageBuilder.api", () => ({
  fetchWebsiteSettings: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  localStorage.clear();
});

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
  fetchWebsiteSettings.mockResolvedValue({ subdomain: "olive-house" });
});

describe("EcommerceThemePage", () => {
  it("loads and publishes storefront colors", async () => {
    render(<EcommerceThemePage />);

    expect(await screen.findByLabelText("Store colors")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Main color"), { target: { value: "#a33a2b" } });
    expect(screen.getByLabelText("Main color").value).toBe("#a33a2b");
    fireEvent.click(screen.getByRole("button", { name: "Publish changes" }));

    await waitFor(() => expect(saveEcommerceTheme).toHaveBeenCalledWith(expect.objectContaining({ accent: "#a33a2b" }), { scope: "authenticated" }));
    expect(await screen.findByText("Store design published")).toBeTruthy();
  });

  it("renders and opens the exact browser-only storefront preview without publishing", async () => {
    const open = vi.spyOn(window, "open").mockImplementation(() => null);
    render(<EcommerceThemePage />);
    await screen.findByLabelText("Store colors");
    expect((await screen.findByTitle("Exact draft storefront preview")).getAttribute("src")).toBe("/site/olive-house/shop?preview=draft");

    fireEvent.change(screen.getByLabelText("Main color"), { target: { value: "#a33a2b" } });
    fireEvent.click(screen.getByRole("button", { name: "Open full preview" }));

    expect(JSON.parse(localStorage.getItem("madar-online-store-theme-preview"))).toMatchObject({ accent: "#a33a2b" });
    expect(open).toHaveBeenCalledWith("/site/olive-house/shop?preview=draft", "_blank", "noopener,noreferrer");
    expect(saveEcommerceTheme).not.toHaveBeenCalled();
  });

  it("rejects incomplete color values with a toast", async () => {
    render(<EcommerceThemePage />);
    await screen.findByLabelText("Store colors");

    fireEvent.change(screen.getByLabelText("Main color"), { target: { value: "#123" } });
    fireEvent.click(screen.getByRole("button", { name: "Publish changes" }));

    expect(await screen.findByText("Check the colors")).toBeTruthy();
    expect(saveEcommerceTheme).not.toHaveBeenCalled();
  });
});
