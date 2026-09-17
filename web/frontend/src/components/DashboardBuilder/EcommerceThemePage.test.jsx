import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EcommerceThemePage from "./EcommerceThemePage";
import { fetchEcommerceCatalog, fetchEcommerceGrowth, fetchEcommerceTheme, saveEcommerceGrowth, saveEcommerceTheme } from "../../services/ecommerceApi";
import { fetchWebsiteSettings } from "../PageBuilder/services/PageBuilder.api";

vi.mock("../../services/ecommerceApi", () => ({
  fetchEcommerceCatalog: vi.fn(),
  fetchEcommerceGrowth: vi.fn(),
  fetchEcommerceTheme: vi.fn(),
  saveEcommerceGrowth: vi.fn(),
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
  fetchEcommerceGrowth.mockResolvedValue({ growth: { announcement_enabled: false, featured_product_ids: [], featured_category_ids: [] } });
  fetchEcommerceCatalog.mockResolvedValue({
    products: [{ id: "product-1", status: "active", translations: { en: { name: "Soap" }, ar: { name: "صابون" } } }],
    categories: [{ id: "category-1", status: "active", translations: { en: { name: "Gifts" }, ar: { name: "هدايا" } } }],
  });
  saveEcommerceGrowth.mockImplementation(async (growth) => ({ growth }));
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

  it("shows only color settings without loading or saving merchandising", async () => {
    render(<EcommerceThemePage />);
    await screen.findByLabelText("Store colors");
    expect(screen.queryByRole("tablist")).toBeNull();
    expect(screen.queryByText("SEO")).toBeNull();
    expect(screen.queryByText("Announcement")).toBeNull();
    expect(screen.queryByText("Featured")).toBeNull();
    expect(screen.queryByRole("button", { name: "Save SEO and merchandising" })).toBeNull();
    expect(fetchEcommerceGrowth).not.toHaveBeenCalled();
    expect(fetchEcommerceCatalog).not.toHaveBeenCalled();
    expect(saveEcommerceGrowth).not.toHaveBeenCalled();
  });

  it("switches preview viewports without publishing and places publishing at the end", async () => {
    render(<EcommerceThemePage />);
    const frame = await screen.findByTitle("Exact draft storefront preview");
    expect(frame.style.width).toBe("1120px");
    fireEvent.click(screen.getByRole("button", {name:"Mobile"}));
    expect(frame.style.width).toBe("390px");
    expect(screen.getByRole("button", {name:"Publish changes"}).closest("footer")).toBeTruthy();
    expect(saveEcommerceTheme).not.toHaveBeenCalled();
  });
});
