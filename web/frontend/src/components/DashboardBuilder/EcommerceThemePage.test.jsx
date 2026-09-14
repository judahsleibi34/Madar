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

  it("loads and explicitly saves localized SEO and merchandising settings", async () => {
    render(<EcommerceThemePage />);
    fireEvent.change(await screen.findByLabelText("Store SEO title (English)"), { target: { value: "Olive shop" } });
    fireEvent.change(screen.getByLabelText("Announcement (Arabic)"), { target: { value: "توصيل محلي" } });
    fireEvent.click(screen.getByLabelText("Show announcement banner"));
    const featuredProducts = screen.getByLabelText("Featured products");
    featuredProducts.options[0].selected = true;
    fireEvent.change(featuredProducts);
    fireEvent.click(screen.getByRole("button", { name: "Save SEO and merchandising" }));

    await waitFor(() => expect(saveEcommerceGrowth).toHaveBeenCalledWith(expect.objectContaining({
      seo_title_en: "Olive shop", announcement_enabled: true, announcement_text_ar: "توصيل محلي", featured_product_ids: ["product-1"],
    })));
    expect(await screen.findByText("Storefront growth settings saved")).toBeTruthy();
  });
});
