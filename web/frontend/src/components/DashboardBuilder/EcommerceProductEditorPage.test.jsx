import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import appI18n from "../../i18n";
import { fetchEcommerceCatalog, saveEcommerceItem, saveEcommerceProductVariants } from "../../services/ecommerceApi";
import { EcommerceProductEditor } from "./EcommerceProductEditorPage";

vi.mock("../../services/ecommerceApi", () => ({
  fetchEcommerceCatalog: vi.fn(),
  saveEcommerceItem: vi.fn(),
  saveEcommerceProductVariants: vi.fn(),
  uploadEcommerceProductImage: vi.fn(),
}));

const catalog = (products = []) => ({
  commerce_currency: "ILS",
  products,
  categories: [],
  tags: [],
});

const renderEditor = (props = {}) => render(
  <MemoryRouter>
    <EcommerceProductEditor
      initialCatalog={catalog()}
      user={{ id: "user-1" }}
      {...props}
    />
  </MemoryRouter>,
);

const nameProduct = (name = "Inventory product") => {
  fireEvent.change(screen.getByLabelText("Name (English)"), { target: { value: name } });
};

const addVariant = ({ name = "Large", color = "Black", hex = "#111111", quantity = "0" } = {}) => {
  fireEvent.click(screen.getByRole("button", { name: "Add variant" }));
  fireEvent.change(screen.getByPlaceholderText("Example: Large, Premium, 128GB"), { target: { value: name } });
  fireEvent.change(screen.getByPlaceholderText("Example: Midnight Black, 44, XL"), { target: { value: color } });
  fireEvent.change(screen.getByLabelText(`Hex value for ${color}`), { target: { value: hex } });
  fireEvent.change(screen.getByLabelText(`${name} ${color} quantity`), { target: { value: quantity } });
};

describe("EcommerceProductEditor variant inventory", () => {
  beforeEach(async () => {
    await appI18n.changeLanguage("en");
    saveEcommerceItem.mockReset();
    saveEcommerceItem.mockResolvedValue({ id: "product-1" });
    saveEcommerceProductVariants.mockReset();
    saveEcommerceProductVariants.mockResolvedValue({ product: { id: "product-1" } });
    fetchEcommerceCatalog.mockReset();
  });

  afterEach(cleanup);

  it("keeps products without variants on the simple inventory path", async () => {
    renderEditor();
    nameProduct("Simple product");

    expect(screen.getByRole("heading", { name: "Inventory" })).toBeTruthy();
    expect(screen.queryByText("Variant attributes")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    expect(saveEcommerceItem.mock.calls[0][2]).toMatchObject({ options: [], variants: [] });
  });

  it("creates free-text variant cards and calculates stock from color quantities", async () => {
    renderEditor();
    nameProduct();
    expect(screen.queryByRole("button", { name: "Save variants" })).toBeNull();
    addVariant({ name: "Large", color: "Black", hex: "#111111", quantity: "4" });
    expect(screen.queryByRole("button", { name: "Save variants" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Add color" }));
    const colorNames = screen.getAllByPlaceholderText("Example: Midnight Black, 44, XL");
    fireEvent.change(colorNames[1], { target: { value: "White" } });
    fireEvent.change(screen.getByLabelText("Hex value for White"), { target: { value: "#FFFFFF" } });
    fireEvent.change(screen.getByLabelText("Large White quantity"), { target: { value: "3" } });

    fireEvent.click(screen.getByRole("button", { name: "Add color" }));
    const updatedColorNames = screen.getAllByPlaceholderText("Example: Midnight Black, 44, XL");
    fireEvent.change(updatedColorNames[2], { target: { value: "Red" } });
    fireEvent.change(screen.getByLabelText("Hex value for Red"), { target: { value: "#DC2626" } });
    fireEvent.change(screen.getByLabelText("Large Red quantity"), { target: { value: "3" } });

    expect(screen.getByText("10 units")).toBeTruthy();
    expect(screen.getByText("Total: 10")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    const payload = saveEcommerceItem.mock.calls[0][2];
    expect(payload.options).toHaveLength(2);
    expect(payload.options.map((option) => option.name_translations.en)).toEqual(["Variant", "Color"]);
    expect(payload.options[0].values.map((value) => value.value_translations.en)).toEqual(["Large"]);
    expect(payload.options[1].values.map((value) => [value.value_translations.en, value.color_hex])).toEqual([
      ["Black", "#111111"],
      ["White", "#FFFFFF"],
      ["Red", "#DC2626"],
    ]);
    expect(payload.variants.map((variant) => variant.inventory_quantity)).toEqual([4, 3, 3]);
    expect(payload.variants.every((variant) => variant.option_value_ids.length === 2)).toBe(true);
  });

  it("never accepts a negative or fractional color quantity", () => {
    renderEditor();
    addVariant();
    const quantity = screen.getByLabelText("Large Black quantity");

    fireEvent.change(quantity, { target: { value: "-9" } });
    expect(quantity.value).toBe("0");
    fireEvent.change(quantity, { target: { value: "3.8" } });
    expect(quantity.value).toBe("3");
  });

  it("does not offer variant-only save before the product exists", () => {
    renderEditor();
    addVariant({ name: "Nike Air Force", color: "44", hex: "#111111", quantity: "0" });

    expect(screen.queryByRole("button", { name: "Save variants" })).toBeNull();
  });

  it("keeps one color per variant and allows removal after another color is added", () => {
    renderEditor();
    addVariant();
    const onlyDelete = screen.getByRole("button", { name: "Remove color" });
    expect(onlyDelete.disabled).toBe(true);
    expect(onlyDelete.title).toBe("Every variant must keep at least one color.");

    fireEvent.click(screen.getByRole("button", { name: "Add color" }));
    const deleteButtons = screen.getAllByRole("button", { name: "Remove color" });
    expect(deleteButtons.every((button) => !button.disabled)).toBe(true);
    fireEvent.click(deleteButtons[1]);
    expect(screen.getAllByPlaceholderText("Example: Midnight Black, 44, XL")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Remove color" }).disabled).toBe(true);
  });

  it("collapses a card while keeping its name and total visible", () => {
    renderEditor();
    addVariant({ name: "Premium", color: "Rose Gold", hex: "#B76E79", quantity: "8" });
    const toggle = screen.getByRole("button", { name: /Premium.*8 units/ });

    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByText("Premium")).toBeTruthy();
    expect(screen.getByText("8 units")).toBeTruthy();
    expect(screen.queryByPlaceholderText("Example: Midnight Black, 44, XL")).toBeNull();
  });

  it("requires a variant name, color name, and valid color value before save", async () => {
    renderEditor();
    nameProduct();
    fireEvent.click(screen.getByRole("button", { name: "Add variant" }));
    const variantName = screen.getByLabelText("Variant name");
    const colorName = screen.getByLabelText("Variant color / Size");
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    expect(await screen.findByText("Enter a name for every variant.")).toBeTruthy();
    expect(saveEcommerceItem).not.toHaveBeenCalled();

    fireEvent.change(variantName, { target: { value: "Kids" } });
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    expect(await screen.findByText("Enter a name for every color.")).toBeTruthy();

    fireEvent.change(colorName, { target: { value: "Custom Blue" } });
    fireEvent.change(screen.getByLabelText("Hex value for Custom Blue"), { target: { value: "#12" } });
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    expect(await screen.findByText("Choose or enter a valid six-digit hex value for every color.")).toBeTruthy();
    expect(saveEcommerceItem).not.toHaveBeenCalled();
  });

  it("hydrates existing Size and Color records into cards without changing sellable identities", async () => {
    const sizeOption = "11111111-1111-4111-8111-111111111111";
    const colorOption = "22222222-2222-4222-8222-222222222222";
    const large = "33333333-3333-4333-8333-333333333333";
    const black = "44444444-4444-4444-8444-444444444444";
    const variantId = "55555555-5555-4555-8555-555555555555";
    const product = {
      id: "product-1", slug: "shirt", sku: null, status: "draft", price: 20, currency: "ILS",
      translations: { en: { name: "Shirt", description: "" }, ar: { name: "", description: "" } },
      attributes: [], images: [], tag_ids: [],
      options: [
        { id: sizeOption, code: "size", name_translations: { en: "Size" }, display_type: "color", values: [{ id: large, code: "large", value_translations: { en: "Large" }, color_hex: "#874040", active: true }] },
        { id: colorOption, code: "color", name_translations: { en: "Color" }, display_type: "color", values: [{ id: black, code: "black", value_translations: { en: "Black" }, color_hex: "#111111", active: true }] },
      ],
      variants: [{ id: variantId, sku: "SHIRT-L-BLACK", inventory_quantity: 4, low_stock_threshold: 2, track_inventory: true, allow_backorder: false, images: [], active: true, option_value_ids: [large, black] }],
    };
    fetchEcommerceCatalog.mockResolvedValue(catalog([product]));
    renderEditor({ initialCatalog: catalog([product]), productId: "product-1" });

    expect(await screen.findByDisplayValue("Large")).toBeTruthy();
    expect(screen.getByDisplayValue("Black")).toBeTruthy();
    expect(screen.getByText("4 units")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Large Black quantity"), { target: { value: "7" } });
    expect(screen.getByRole("button", { name: "Save variants" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save variants" }));

    await waitFor(() => expect(saveEcommerceProductVariants).toHaveBeenCalledOnce());
    expect(saveEcommerceItem).not.toHaveBeenCalled();
    const [savedProductId, payload] = saveEcommerceProductVariants.mock.calls[0];
    expect(savedProductId).toBe("product-1");
    expect(payload.options.map((option) => option.id)).toEqual([sizeOption, colorOption]);
    expect(payload.variants[0]).toMatchObject({ id: variantId, sku: "SHIRT-L-BLACK", inventory_quantity: 7, option_value_ids: [large, black] });
  });

  it("localizes the redesigned inventory editor and preserves RTL direction", async () => {
    await appI18n.changeLanguage("ar");
    const { container } = renderEditor();
    expect(container.querySelector("form").getAttribute("dir")).toBe("rtl");
    expect(screen.getByRole("heading", { name: "الأنواع والمخزون" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "إضافة نوع" })).toBeTruthy();
  });
});
