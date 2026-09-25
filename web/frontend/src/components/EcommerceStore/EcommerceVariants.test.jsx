import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import EcommerceStorefront from "./EcommerceStorefront";
import i18n from "../../i18n";
import { fetchPublicEcommerceCatalog, fetchPublicEcommerceProduct } from "../../services/ecommerceApi";

vi.mock("../../services/ecommerceApi", () => ({
  fetchPublicEcommerceCatalog: vi.fn(), fetchPublicEcommerceProduct: vi.fn(),
  fetchPublicEcommerceProfile: vi.fn(), fetchPublicEcommerceDeliveryAreas: vi.fn(() => Promise.resolve({ areas: [] })),
  fetchPublicEcommerceOrderConfirmation: vi.fn(), createPublicEcommerceOrder: vi.fn(),
  fetchPublicEcommerceLoyalty: vi.fn(() => Promise.reject(new Error("guest"))),
  fetchPublicEcommerceDiscounts: vi.fn(() => Promise.resolve({ conditions:[] })),
  fetchPublicStoreAccount: vi.fn(() => Promise.resolve({ logged_in: false, user: null })),
  reconcilePublicEcommerceCart: vi.fn(),
}));

const product = { id: "product-1", slug: "shirt", name: "Shirt", brand: "Noura Studio", price: "20.00", compare_at_price: "25.00", currency: "ILS", in_stock: true, images: ["https://example.com/base.webp"] };
const color = { id: "option-color", code: "color", name: "Color", required: true, values: [{ id: "black", code: "black", value: "Black" }, { id: "white", code: "white", value: "White" }] };
const size = { id: "option-size", code: "size", name: "Size", required: true, values: [{ id: "small", code: "s", value: "S" }, { id: "large", code: "l", value: "L" }] };

afterEach(() => { cleanup(); vi.clearAllMocks(); localStorage.clear(); i18n.changeLanguage("en"); });

describe("merchant-defined ecommerce variants", () => {
  it("renders generic color presentation as accessible labeled swatches", async () => {
    fetchPublicEcommerceProduct.mockResolvedValue({ site: { brand: "Store" }, product, category: { name: "Women" }, tags: [], attributes: [], options: [{
      ...color, display_type: "color", values: [
        { id: "black", code: "black", value: "Black", color_hex: "#111111" },
        { id: "white", code: "white", value: "White", color_hex: "#FFFFFF" },
      ],
    }], variants: [{ id: "black-only", sku: "BLACK", option_value_ids: ["black"], price: "20.00", in_stock: true, images: [] }] });
    render(<MemoryRouter initialEntries={["/shop/product/shirt"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);
    const black = await screen.findByRole("radio", { name: "Black" });
    const white = screen.getByRole("radio", { name: /White/ });
    const productName = screen.getByRole("heading", { level: 1, name: "Shirt" });
    const productTag = screen.getByRole("heading", { level: 2, name: "Noura Studio / Women" });
    expect(productName.compareDocumentPosition(productTag) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(black.closest("label").querySelector(".live-store-color-swatch").style.backgroundColor).toBe("rgb(17, 17, 17)");
    expect(white.disabled).toBe(true);
    fireEvent.click(black);
    expect(black.checked).toBe(true);
  });

  it("requires an explicit valid combination and updates price, image, and cart identity", async () => {
    fetchPublicEcommerceProduct.mockResolvedValue({ site: { brand: "Store" }, product, category: null, tags: [], attributes: [{ id: "a1", name: "Material", value: "Cotton" }], options: [color, size], variants: [
      { id: "variant-black-small", sku: "SHIRT-B-S", option_value_ids: ["black", "small"], price: "20.00", in_stock: true, images: [] },
      { id: "variant-white-large", sku: "SHIRT-W-L", option_value_ids: ["white", "large"], price: "24.00", compare_at_price: "28.00", in_stock: true, images: ["https://example.com/white.webp"] },
    ] });
    fetchPublicEcommerceCatalog.mockResolvedValue({ site: { brand: "Store" }, catalog: { categories: [], tags: [], products: [], pagination: { page: 1, pages: 1, total: 0, limit: 12 } } });

    render(<MemoryRouter initialEntries={["/shop/product/shirt"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);

    const add = await screen.findByRole("button", { name: "Choose options" });
    expect(add.disabled).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: "White" }));
    expect(screen.getByRole("radio", { name: "S" }).closest("label").classList.contains("is-incompatible")).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: "L" }));
    expect(screen.getByText("₪24.00")).toBeTruthy();
    expect(screen.getByAltText("Shirt 1").getAttribute("src")).toContain("white.webp");
    fireEvent.click(screen.getByRole("button", { name: "Add to cart" }));
    fireEvent.click(screen.getByRole("button", { name: "Open cart, 1 item" }));
    expect(screen.getByText("Color: White · Size: L")).toBeTruthy();
    const stored = JSON.parse(localStorage.getItem("madar-store-cart:demo"));
    expect(stored[0]).toMatchObject({ id: "product-1", variant_id: "variant-white-large" });
  });

  it("keeps the variant matrix hidden and selects a combination through expandable options", async () => {
    fetchPublicEcommerceProduct.mockResolvedValue({
      site: { brand: "Store" },
      product: { ...product, track_inventory: true, inventory_quantity: 0 },
      category: null,
      tags: [],
      attributes: [{ id: "a1", name: "Material", value: "Cotton" }],
      options: [color, size],
      variants: [
        { id: "black-small", sku: "SHIRT-B-S", option_value_ids: ["black", "small"], price: "20.00", track_inventory: true, inventory_quantity: 5, allow_backorder: false, in_stock: true, images: [] },
        { id: "white-large", sku: "SHIRT-W-L", option_value_ids: ["white", "large"], price: "24.00", track_inventory: true, inventory_quantity: 7, allow_backorder: false, in_stock: true, images: [] },
        { id: "white-small", sku: "SHIRT-W-S", option_value_ids: ["white", "small"], price: "22.00", track_inventory: true, inventory_quantity: 0, allow_backorder: false, in_stock: false, images: [] },
      ],
    });

    render(<MemoryRouter initialEntries={["/shop/product/shirt"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);

    expect(await screen.findByRole("radio", { name: "White" })).toBeTruthy();
    expect(screen.queryByText("12 items available")).toBeNull();
    expect(screen.queryByText("7 items available")).toBeNull();
    expect(screen.queryByText("2 of 3 variants available")).toBeNull();
    expect(screen.getByRole("heading", { name: "Specifications" })).toBeTruthy();
    expect(screen.getByText("Material")).toBeTruthy();
    expect(screen.getByText("Cotton")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Variants & stock" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Select White/ })).toBeNull();

    fireEvent.click(screen.getByRole("radio", { name: "White" }));
    expect(screen.queryByText("7 items available")).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "L" }));
    expect(screen.getByText("7 items available")).toBeTruthy();
    expect(screen.getAllByText("7 items available")).toHaveLength(1);
    expect(document.querySelector(".live-store-variant-meta")?.textContent).not.toContain("items available");
    fireEvent.click(screen.getByRole("button", { name: "Add to cart" }));
    expect(JSON.parse(localStorage.getItem("madar-store-cart:demo"))[0]).toMatchObject({ variant_id: "white-large" });
  });

  it("loads a legacy simple-product cart line without a variant", async () => {
    localStorage.setItem("madar-store-cart:demo", JSON.stringify([{ ...product, quantity: 1 }]));
    fetchPublicEcommerceCatalog.mockResolvedValue({ site: { brand: "Store" }, catalog: { categories: [], tags: [], products: [], pagination: { page: 1, pages: 1, total: 0, limit: 12 } } });
    render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Open cart, 1 item" }));
    expect(screen.getByText("Shirt")).toBeTruthy();
  });
});
  it("presents localized Arabic attributes, options, and fallback values in RTL", async () => {
    await i18n.changeLanguage("ar");
    fetchPublicEcommerceProduct.mockResolvedValue({
      site: { brand: "متجر" },
      product: { ...product, name: "قميص" },
      category: null, tags: [],
      attributes: [{ id: "a1", name: "الخامة", value: "قطن" }],
      options: [
        { id: "option-color", code: "color", name: "اللون", required: true, values: [{ id: "black", code: "black", value: "أسود" }] },
        { id: "option-size", code: "size", name: "المقاس", required: true, values: [{ id: "large", code: "l", value: "L" }] },
      ],
      variants: [{ id: "variant-1", sku: "SHIRT-B-L", option_value_ids: ["black", "large"], price: "20", in_stock: true, images: [] }],
    });

    render(<MemoryRouter initialEntries={["/shop/product/shirt"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);

    expect(await screen.findByRole("heading", { level: 1, name: "قميص" })).toBeTruthy();
    expect(screen.getByText("الخامة")).toBeTruthy();
    expect(screen.getByText("قطن")).toBeTruthy();
    const localizedOptions = screen.getAllByRole("radio");
    expect(localizedOptions).toHaveLength(2);
    fireEvent.click(localizedOptions[0]);
    expect(screen.getByRole("radio", { name: "L" })).toBeTruthy();
    expect(document.querySelector(".live-store").getAttribute("dir")).toBe("rtl");
  });
