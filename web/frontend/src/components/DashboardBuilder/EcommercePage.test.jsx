import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EcommercePage from "./EcommercePage";
import {
  deleteEcommerceItem,
  fetchEcommerceCatalog,
  saveEcommerceItem,
  uploadEcommerceProductImage,
} from "../../services/ecommerceApi";
import { clearEcommerceCatalogCache, writeEcommerceCatalogCache } from "./utils/ecommerceCatalogCache";

vi.mock("../../services/ecommerceApi", () => ({
  fetchEcommerceCatalog: vi.fn(),
  saveEcommerceItem: vi.fn(),
  deleteEcommerceItem: vi.fn(),
  uploadEcommerceProductImage: vi.fn(),
}));

afterEach(() => {
  cleanup();
  clearEcommerceCatalogCache("authenticated");
});

beforeEach(() => {
  window.localStorage.clear();
  vi.clearAllMocks();
  fetchEcommerceCatalog.mockResolvedValue({ tags: [], categories: [], products: [] });
  saveEcommerceItem.mockResolvedValue({});
  deleteEcommerceItem.mockResolvedValue(null);
  uploadEcommerceProductImage.mockResolvedValue("/uploads/tenant_7/builder_assets/0123456789abcdef0123456789abcdef.webp");
});

describe("EcommercePage", () => {
  it("shows cards for every catalog status", async () => {
    fetchEcommerceCatalog.mockResolvedValue({
      tags: [
        { id: "tag-draft", slug: "draft", status: "draft", translations: { en: { name: "Draft tag" } } },
        { id: "tag-active", slug: "active", status: "active", translations: { en: { name: "Active tag" } } },
        { id: "tag-inactive", slug: "inactive", status: "inactive", translations: { en: { name: "Inactive tag" } } },
        { id: "tag-archived", slug: "archived", status: "archived", translations: { en: { name: "Archived tag" } } },
      ],
      categories: [],
      products: [],
    });

    const { container } = render(<EcommercePage section="tags" />);
    await screen.findByText("Draft tag");
    const cards = [...container.querySelectorAll(".ecommerce-summary-card")];
    expect(cards.map((card) => card.textContent)).toEqual([
      "Total tags4",
      "Draft1",
      "Active1",
      "Inactive1",
      "Archived1",
    ]);
  });

  it("lets users hide and restore overview cards", async () => {
    render(<EcommercePage section="tags" />);
    await screen.findByText("No tags yet");
    fireEvent.click(screen.getByRole("button", { name: "Customize tag cards" }));
    expect(screen.getByText("Tag cards")).toBeTruthy();
    fireEvent.click(screen.getByRole("checkbox", { name: "Archived" }));
    expect(document.querySelectorAll(".ecommerce-summary-card")).toHaveLength(4);
    expect(JSON.parse(window.localStorage.getItem("madar-ecommerce-summary-cards-v1:authenticated:tags"))).toEqual(["archived"]);
    fireEvent.click(screen.getByRole("button", { name: "Show all" }));
    expect(document.querySelectorAll(".ecommerce-summary-card")).toHaveLength(5);
  });

  it("shows cached products immediately while refreshing in the background", () => {
    writeEcommerceCatalogCache("authenticated", {
      tags: [],
      categories: [],
      products: [{
        id: "cached-product",
        slug: "cached-product",
        sku: "CACHE-1",
        currency: "USD",
        price: 10,
        status: "active",
        translations: { en: { name: "Cached product" } },
      }],
    });
    fetchEcommerceCatalog.mockReturnValue(new Promise(() => {}));

    render(<EcommercePage section="products" />);

    expect(screen.getByText("Cached product")).toBeTruthy();
    expect(screen.queryByText(/Loading catalog/)).toBeNull();
  });

  it("uses a toast instead of browser validation messages", async () => {
    render(<EcommercePage section="tags" />);
    await screen.findByText("No tags yet");

    fireEvent.click(screen.getByRole("button", { name: "Add tag" }));
    const formElement = screen.getByRole("button", { name: "Save" }).closest("form");
    expect(formElement.noValidate).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Complete the required fields")).toBeTruthy();
    expect(screen.getByText("Enter english name before saving.")).toBeTruthy();
    expect(saveEcommerceItem).not.toHaveBeenCalled();
  });

  it("generates the slug from the English name until it is manually edited", async () => {
    render(<EcommercePage section="tags" />);
    await screen.findByText("No tags yet");

    fireEvent.click(screen.getByRole("button", { name: "Add tag" }));
    const englishName = screen.getAllByLabelText("Name")[0];
    const slug = screen.getByLabelText("Slug");
    fireEvent.change(englishName, { target: { value: "Summer & Self Care" } });
    expect(slug.value).toBe("summer-self-care");

    fireEvent.change(slug, { target: { value: "seasonal" } });
    fireEvent.change(englishName, { target: { value: "Summer Essentials" } });
    expect(slug.value).toBe("seasonal");
  });

  it("creates a tag with English and Arabic translations", async () => {
    render(<EcommercePage section="tags" />);
    await screen.findByText("No tags yet");

    fireEvent.click(screen.getByRole("button", { name: "Add tag" }));
    const nameFields = screen.getAllByLabelText("Name");
    fireEvent.change(nameFields[0], { target: { value: "Summer" } });
    fireEvent.change(nameFields[1], { target: { value: "الصيف" } });
    fireEvent.change(screen.getByLabelText("Slug"), { target: { value: "summer" } });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "active" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    expect(saveEcommerceItem).toHaveBeenCalledWith(
      "tags",
      undefined,
      expect.objectContaining({
        translations: {
          en: { name: "Summer", description: "" },
          ar: { name: "الصيف", description: "" },
        },
      }),
      { scope: "authenticated" },
    );
  });

  it("offers parent categories and routes product creation to the full editor", async () => {
    fetchEcommerceCatalog.mockResolvedValue({
      tags: [{ id: "tag-1", slug: "summer", status: "active", translations: { en: { name: "Summer" } } }],
      categories: [{ id: "category-1", slug: "clothes", status: "active", translations: { en: { name: "Clothes" } } }],
      products: [],
    });

    const { rerender } = render(<EcommercePage section="categories" />);
    expect(await screen.findByRole("button", { name: "Customize category cards" })).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Add category" }));
    expect(screen.getByLabelText("Parent category")).toBeTruthy();
    expect(screen.getByLabelText("Display position").value).toBe("");
    expect(screen.getByLabelText("Status").value).toBe("");
    expect(screen.getByLabelText("Status").querySelector('option[value="inactive"]')?.textContent).toBe("Inactive");
    expect(screen.getByLabelText("Slug").value).toBe("");
    expect(screen.getByText("Lower numbers appear first. Use 0 for the first position.")).toBeTruthy();
    expect(screen.queryByLabelText("Sort order")).toBeNull();
    expect(screen.queryByPlaceholderText("generated-from-name")).toBeNull();

    rerender(<EcommercePage key="products" section="products" />);
    expect(await screen.findByRole("button", { name: "Customize product cards" })).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Add product" }));
    expect(await screen.findByRole("dialog", { name: "New product" })).toBeTruthy();
    expect(screen.queryByText("Loading product editor...")).toBeNull();
    expect(screen.getByRole("heading", { name: "New product" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Specifications" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Options & Variants" })).toBeTruthy();
    expect(screen.getByText("This product has no options")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Save product" })).toHaveLength(1);
    expect(screen.queryByText("Full product editor")).toBeNull();
  });
});
  it("shows aggregate stock counts and filters simple and variant products", async () => {
    fetchEcommerceCatalog.mockResolvedValue({
      tags: [], categories: [], stock_summary: { low_stock: 2, out_of_stock: 2 },
      products: [
        { id: "low", slug: "low", sku: "LOW", price: 10, currency: "ILS", status: "active", translations: { en: { name: "Low simple" } }, options: [], inventory_status: "low_stock", low_stock_count: 1, out_of_stock_count: 0, has_low_stock: true, has_out_of_stock: false },
        { id: "out", slug: "out", sku: "OUT", price: 10, currency: "ILS", status: "active", translations: { en: { name: "Out simple" } }, options: [], inventory_status: "out_of_stock", low_stock_count: 0, out_of_stock_count: 1, has_low_stock: false, has_out_of_stock: true },
        { id: "mixed", slug: "mixed", sku: "MIX", price: 10, currency: "ILS", status: "active", translations: { en: { name: "Mixed variants" } }, options: [{ id: "size" }], inventory_status: "low_stock", low_stock_count: 1, out_of_stock_count: 1, has_low_stock: true, has_out_of_stock: true },
        { id: "healthy", slug: "healthy", sku: "OK", price: 10, currency: "ILS", status: "active", translations: { en: { name: "Healthy" } }, options: [], inventory_status: "healthy", low_stock_count: 0, out_of_stock_count: 0, has_low_stock: false, has_out_of_stock: false },
      ],
    });

    render(<EcommercePage section="products" />);

    expect(await screen.findByText("Low simple")).toBeTruthy();
    const lowSummary = screen.getAllByText("Low stock").find((node) => node.closest(".ecommerce-summary-card"));
    const outSummary = screen.getAllByText("Out of stock").find((node) => node.closest(".ecommerce-summary-card"));
    expect(lowSummary.closest(".ecommerce-summary-card").textContent).toContain("2");
    expect(outSummary.closest(".ecommerce-summary-card").textContent).toContain("2");
    expect(screen.getByText(/1 low · 1 out/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Low stock" }));
    expect(screen.getByText("Low simple")).toBeTruthy();
    expect(screen.getByText("Mixed variants")).toBeTruthy();
    expect(screen.queryByText("Out simple")).toBeNull();
    expect(screen.queryByText("Healthy")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Out of stock" }));
    expect(screen.getByText("Out simple")).toBeTruthy();
    expect(screen.getByText("Mixed variants")).toBeTruthy();
    expect(screen.queryByText("Low simple")).toBeNull();
  });
