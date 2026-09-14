import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import EcommerceStorefront from "./EcommerceStorefront";
import i18n from "../../i18n";
import { fetchPublicEcommerceCatalog, fetchPublicEcommerceProduct } from "../../services/ecommerceApi";

vi.mock("../../services/ecommerceApi", () => ({
  fetchPublicEcommerceCatalog: vi.fn(), fetchPublicEcommerceProduct: vi.fn(),
  fetchPublicEcommerceProfile: vi.fn(), fetchPublicEcommerceDeliveryAreas: vi.fn(),
  fetchPublicEcommerceOrderConfirmation: vi.fn(), createPublicEcommerceOrder: vi.fn(),
  fetchPublicEcommerceLoyalty: vi.fn(() => Promise.reject(new Error("guest"))),
  reconcilePublicEcommerceCart: vi.fn(),
}));

const product = { id: "product-1", slug: "shirt", name: "Shirt", price: "20.00", compare_at_price: "25.00", currency: "ILS", in_stock: true, images: ["https://example.com/base.webp"] };
const color = { id: "option-color", code: "color", name: "Color", required: true, values: [{ id: "black", code: "black", value: "Black" }, { id: "white", code: "white", value: "White" }] };
const size = { id: "option-size", code: "size", name: "Size", required: true, values: [{ id: "small", code: "s", value: "S" }, { id: "large", code: "l", value: "L" }] };

afterEach(() => { cleanup(); vi.clearAllMocks(); localStorage.clear(); i18n.changeLanguage("en"); });

describe("merchant-defined ecommerce variants", () => {
  it("requires an explicit valid combination and updates price, image, and cart identity", async () => {
    fetchPublicEcommerceProduct.mockResolvedValue({ site: { brand: "Store" }, product, category: null, tags: [], attributes: [{ id: "a1", name: "Material", value: "Cotton" }], options: [color, size], variants: [
      { id: "variant-black-small", sku: "SHIRT-B-S", option_value_ids: ["black", "small"], price: "20.00", in_stock: true, images: [] },
      { id: "variant-white-large", sku: "SHIRT-W-L", option_value_ids: ["white", "large"], price: "24.00", compare_at_price: "28.00", in_stock: true, images: ["https://example.com/white.webp"] },
    ] });
    fetchPublicEcommerceCatalog.mockResolvedValue({ site: { brand: "Store" }, catalog: { categories: [], tags: [], products: [], pagination: { page: 1, pages: 1, total: 0, limit: 12 } } });

    render(<MemoryRouter initialEntries={["/store/demo/product/shirt"]}><Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes></MemoryRouter>);

    const add = await screen.findByRole("button", { name: "Choose options" });
    expect(add.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "White" }));
    expect(screen.getByRole("button", { name: "S" }).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "L" }));
    expect(screen.getByText("₪24.00")).toBeTruthy();
    expect(screen.getByAltText("Shirt 1").getAttribute("src")).toContain("white.webp");
    fireEvent.click(screen.getByRole("button", { name: "Add to cart" }));
    fireEvent.click(screen.getByRole("button", { name: "Open cart, 1 item" }));
    expect(screen.getByText("Color: White · Size: L")).toBeTruthy();
    const stored = JSON.parse(localStorage.getItem("madar-store-cart:demo"));
    expect(stored[0]).toMatchObject({ id: "product-1", variant_id: "variant-white-large" });
  });

  it("loads a legacy simple-product cart line without a variant", async () => {
    localStorage.setItem("madar-store-cart:demo", JSON.stringify([{ ...product, quantity: 1 }]));
    fetchPublicEcommerceCatalog.mockResolvedValue({ site: { brand: "Store" }, catalog: { categories: [], tags: [], products: [], pagination: { page: 1, pages: 1, total: 0, limit: 12 } } });
    render(<MemoryRouter initialEntries={["/store/demo"]}><Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes></MemoryRouter>);
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

    render(<MemoryRouter initialEntries={["/store/demo/product/shirt"]}><Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes></MemoryRouter>);

    expect(await screen.findByRole("heading", { level: 1, name: "قميص" })).toBeTruthy();
    expect(screen.getByText("الخامة")).toBeTruthy();
    expect(screen.getByText("قطن")).toBeTruthy();
    expect(screen.getByRole("button", { name: "أسود" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "L" })).toBeTruthy();
    expect(document.querySelector(".live-store").getAttribute("dir")).toBe("rtl");
  });
