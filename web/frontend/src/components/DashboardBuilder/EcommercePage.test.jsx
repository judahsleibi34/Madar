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

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ i18n: { resolvedLanguage: "en" } }),
}));

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
  vi.clearAllMocks();
  fetchEcommerceCatalog.mockResolvedValue({ tags: [], categories: [], products: [] });
  saveEcommerceItem.mockResolvedValue({});
  deleteEcommerceItem.mockResolvedValue(null);
  uploadEcommerceProductImage.mockResolvedValue("/uploads/tenant_7/builder_assets/0123456789abcdef0123456789abcdef.webp");
});

describe("EcommercePage", () => {
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

  it("offers parent categories and complete product data groups", async () => {
    fetchEcommerceCatalog.mockResolvedValue({
      tags: [{ id: "tag-1", slug: "summer", status: "active", translations: { en: { name: "Summer" } } }],
      categories: [{ id: "category-1", slug: "clothes", status: "active", translations: { en: { name: "Clothes" } } }],
      products: [],
    });

    const { rerender } = render(<EcommercePage section="categories" />);
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
    fireEvent.click(await screen.findByRole("button", { name: "Add product" }));
    expect(screen.getByText("Pricing")).toBeTruthy();
    expect(screen.getByText("Inventory")).toBeTruthy();
    expect(screen.getByText("Images and weight")).toBeTruthy();
    expect(screen.queryByText("SEO")).toBeNull();
    expect(screen.getByLabelText("Regular price").value).toBe("");
    expect(screen.getByLabelText(/Discounted price/).value).toBe("");
    expect(screen.queryByLabelText("Cost price")).toBeNull();
    expect(screen.queryByLabelText("Compare-at price")).toBeNull();
    expect(screen.getByLabelText("Currency").value).toBe("");
    expect(screen.getByLabelText("Product type").value).toBe("");
    expect(screen.getByLabelText("SKU").required).toBe(false);
    expect(screen.getByLabelText("Barcode").required).toBe(false);
    expect(screen.getByText("Leave empty and Madar will generate a unique product code.")).toBeTruthy();
    expect(screen.getByText("Enter the printed barcode only when the product has one.")).toBeTruthy();
    expect(screen.getByLabelText("Status").querySelector('option[value="inactive"]')?.textContent).toBe("Inactive");
    expect(screen.getByLabelText(/Current stock/).value).toBe("");
    expect(screen.getByLabelText(/Warn me when stock reaches/).value).toBe("");
    expect(screen.getByText("How many items are available now.")).toBeTruthy();
    expect(screen.getByText("Madar will show a low-stock warning at this number or below.")).toBeTruthy();
    expect(screen.getByLabelText("Track inventory").closest(".ecommerce-check-row")).toBeTruthy();
    expect(screen.getByLabelText(/Let customers order when sold out/).closest(".ecommerce-check-row")).toBeTruthy();
    expect(screen.queryByLabelText("Requires shipping")).toBeNull();
    expect(screen.queryByLabelText("Taxable")).toBeNull();
    expect(screen.getByLabelText("Unit").value).toBe("");
    expect(screen.queryByPlaceholderText("generated-from-name")).toBeNull();
    expect(screen.queryByText("Image URLs (one per line)")).toBeNull();
    expect(screen.getByText("The first image will be the main product image.")).toBeTruthy();
    const productImage = new File(["image"], "product.webp", { type: "image/webp" });
    fireEvent.change(screen.getByLabelText("Upload product images"), { target: { files: [productImage] } });
    expect(await screen.findByAltText("Product image 1")).toBeTruthy();
    expect(uploadEcommerceProductImage).toHaveBeenCalledWith(productImage);
    fireEvent.click(screen.getByRole("button", { name: "Remove product image 1" }));
    expect(screen.queryByAltText("Product image 1")).toBeNull();
  });
});
