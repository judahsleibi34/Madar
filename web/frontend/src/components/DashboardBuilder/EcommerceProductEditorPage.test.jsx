import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import appI18n from "../../i18n";
import { fetchEcommerceCatalog, saveEcommerceItem, saveEcommerceProductVariants, uploadEcommerceProductImage } from "../../services/ecommerceApi";
import CommerceActionToast from "./CommerceActionToast";
import { EcommerceProductEditor } from "./EcommerceProductEditorPage";

vi.mock("../../services/ecommerceApi", () => ({
  fetchEcommerceCatalog: vi.fn(),
  saveEcommerceItem: vi.fn(),
  saveEcommerceProductVariants: vi.fn(),
  uploadEcommerceProductImage: vi.fn(),
}));

const catalog = (products = [], categories = []) => ({
  commerce_currency: "ILS",
  products,
  categories,
  tags: [],
});

const renderEditor = (props = {}) => render(
  <MemoryRouter>
    <CommerceActionToast />
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
  fireEvent.click(screen.getByRole("button", { name: "Add size" }));
  fireEvent.change(screen.getByPlaceholderText("Example: S, M, L, XL"), { target: { value: name } });
  fireEvent.change(screen.getByPlaceholderText("Example: Black, White, Red"), { target: { value: color } });
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
    uploadEcommerceProductImage.mockReset();
    uploadEcommerceProductImage.mockResolvedValue("/uploads/tenant_7/builder_assets/product.webp");
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

  it("saves every checked product category and keeps the first as the compatible primary category", async () => {
    const categories = [
      { id: "11111111-1111-4111-8111-111111111111", translations: { en: { name: "Women" } } },
      { id: "22222222-2222-4222-8222-222222222222", translations: { en: { name: "Outerwear" } } },
    ];
    renderEditor({ initialCatalog: catalog([], categories) });
    nameProduct("Coat");

    fireEvent.click(screen.getByRole("checkbox", { name: "Women" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Outerwear" }));
    expect(screen.getByText("2 categories selected")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    expect(saveEcommerceItem.mock.calls[0][2]).toMatchObject({
      category_id: categories[0].id,
      category_ids: categories.map((category) => category.id),
    });
  });

  it("keeps the embedded close control inside the unified header", () => {
    const onClose = vi.fn();
    renderEditor({ embedded: true, onClose });

    const closeButton = screen.getByRole("button", { name: "Close" });
    expect(closeButton.closest("header")?.classList.contains("ecommerce-product-editor-modal-header")).toBe(true);
    fireEvent.click(closeButton);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("rejects numeric-only or formatted product names", async () => {
    renderEditor();
    nameProduct("12345");
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    expect(await screen.findByText(/Names must contain at least one letter/)).toBeTruthy();
    expect(saveEcommerceItem).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));

    nameProduct("<b>Chair</b>");
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    expect(await screen.findByText(/Use plain text only/)).toBeTruthy();
    expect(saveEcommerceItem).not.toHaveBeenCalled();
  });

  it("explains incomplete specification rows before saving", async () => {
    renderEditor();
    nameProduct("Chair");
    fireEvent.click(screen.getByRole("button", { name: "Add specification" }));
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    expect(await screen.findByText("Enter an English name for every specification you added.")).toBeTruthy();
    expect(saveEcommerceItem).not.toHaveBeenCalled();
  });

  it("shows a specific fallback when the API rejects product fields", async () => {
    const error = new Error("internal validation detail");
    error.status = 422;
    saveEcommerceItem.mockRejectedValue(error);
    renderEditor();
    nameProduct("Chair");
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    expect(await screen.findByText(/The server rejected one or more product fields/)).toBeTruthy();
    expect(document.body.textContent).not.toContain("internal validation detail");
    expect(document.querySelector(".ecommerce-editor-error")).toBeNull();
  });

  it("identifies the invalid product area from structured 422 errors", async () => {
    const error = new Error("internal validation detail");
    error.status = 422;
    error.data = {
      detail: [{ loc: ["body", "category_ids", 0], msg: "Input should be a valid UUID" }],
    };
    saveEcommerceItem.mockRejectedValue(error);
    renderEditor();
    nameProduct("Chair");
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    expect(await screen.findByText(/selected categories are invalid or no longer available/i)).toBeTruthy();
    expect(document.body.textContent).not.toContain("Input should be a valid UUID");
  });

  it("attempts a one MiB image and explains an unexpected server 413", async () => {
    const error = new Error("Request body too large");
    error.status = 413;
    uploadEcommerceProductImage.mockRejectedValue(error);
    renderEditor();
    const image = new File([new Uint8Array(1024 * 1024)], "product.jpg", { type: "image/jpeg" });

    fireEvent.change(screen.getByLabelText("Upload product media"), {
      target: { files: [image] },
    });

    await waitFor(() => expect(uploadEcommerceProductImage).toHaveBeenCalledWith(image));
    expect((await screen.findAllByText(/allowed limit is 25 MB per file/i)).length).toBeGreaterThan(0);
  });

  it("creates free-text variant cards and calculates stock from color quantities", async () => {
    renderEditor();
    nameProduct();
    expect(screen.queryByRole("button", { name: "Save variants" })).toBeNull();
    addVariant({ name: "Large", color: "Black", hex: "#111111", quantity: "4" });
    expect(screen.queryByRole("button", { name: "Save variants" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Add color" }));
    const colorNames = screen.getAllByPlaceholderText("Example: Black, White, Red");
    fireEvent.change(colorNames[1], { target: { value: "White" } });
    fireEvent.change(screen.getByLabelText("Hex value for White"), { target: { value: "#FFFFFF" } });
    fireEvent.change(screen.getByLabelText("Large White quantity"), { target: { value: "3" } });

    fireEvent.click(screen.getByRole("button", { name: "Add color" }));
    const updatedColorNames = screen.getAllByPlaceholderText("Example: Black, White, Red");
    fireEvent.change(updatedColorNames[2], { target: { value: "Red" } });
    fireEvent.change(screen.getByLabelText("Hex value for Red"), { target: { value: "#DC2626" } });
    fireEvent.change(screen.getByLabelText("Large Red quantity"), { target: { value: "3" } });

    expect(screen.getByText("10 units")).toBeTruthy();
    expect(screen.getByText("Total: 10")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    const payload = saveEcommerceItem.mock.calls[0][2];
    expect(payload.options).toHaveLength(2);
    expect(payload.options.map((option) => option.name_translations.en)).toEqual(["Size", "Color"]);
    expect(payload.options.map((option) => option.code)).toEqual(["size", "color"]);
    expect(payload.options[0].values.map((value) => value.value_translations.en)).toEqual(["Large"]);
    expect(payload.options[1].values.map((value) => [value.value_translations.en, value.color_hex])).toEqual([
      ["Black", "#111111"],
      ["White", "#FFFFFF"],
      ["Red", "#DC2626"],
    ]);
    expect(payload.variants.map((variant) => variant.inventory_quantity)).toEqual([4, 3, 3]);
    expect(payload.variants.every((variant) => variant.option_value_ids.length === 2)).toBe(true);
  });

  it("keeps inventory controls visible and applies them to generated variants", async () => {
    renderEditor();
    nameProduct();
    addVariant({ name: "Large", color: "Black", hex: "#111111", quantity: "4" });

    const trackInventory = screen.getByRole("checkbox", { name: "Track inventory" });
    const allowBackorder = screen.getByRole("checkbox", { name: "Let customers order when sold out" });
    const lowStockThreshold = screen.getByRole("spinbutton", { name: "Warn me when stock reaches" });
    expect(screen.getAllByText("Starting stock").length).toBeGreaterThan(0);
    expect(trackInventory.checked).toBe(true);
    fireEvent.change(lowStockThreshold, { target: { value: "2" } });
    fireEvent.click(trackInventory);
    fireEvent.click(allowBackorder);
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    const variants = saveEcommerceItem.mock.calls[0][2].variants;
    expect(variants.every((variant) => variant.track_inventory === false)).toBe(true);
    expect(variants.every((variant) => variant.allow_backorder === true)).toBe(true);
    expect(variants.every((variant) => variant.low_stock_threshold === 2)).toBe(true);
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
    expect(onlyDelete.title).toBe("Every size must keep at least one color.");

    fireEvent.click(screen.getByRole("button", { name: "Add color" }));
    const deleteButtons = screen.getAllByRole("button", { name: "Remove color" });
    expect(deleteButtons.every((button) => !button.disabled)).toBe(true);
    fireEvent.click(deleteButtons[1]);
    expect(screen.getAllByPlaceholderText("Example: Black, White, Red")).toHaveLength(1);
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
    expect(screen.queryByPlaceholderText("Example: Black, White, Red")).toBeNull();
  });

  it("requires a variant name, color name, and valid color value before save", async () => {
    renderEditor();
    nameProduct();
    fireEvent.click(screen.getByRole("button", { name: "Add size" }));
    const variantName = screen.getByLabelText("Size");
    const colorName = screen.getByLabelText("Color name");
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    expect(await screen.findByText("Enter a size for every row.")).toBeTruthy();
    expect(saveEcommerceItem).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));

    fireEvent.change(variantName, { target: { value: "Kids" } });
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    expect(await screen.findByText("Enter a name for every color.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss notification" }));

    fireEvent.change(colorName, { target: { value: "Custom Blue" } });
    fireEvent.change(screen.getByLabelText("Hex value for Custom Blue"), { target: { value: "#12" } });
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    expect(await screen.findByText("Choose or enter a valid six-digit hex value for every color.")).toBeTruthy();
    expect(saveEcommerceItem).not.toHaveBeenCalled();
  });

  it("allows a numeric color name and loads a black swatch by default", async () => {
    renderEditor();
    nameProduct();
    fireEvent.click(screen.getByRole("button", { name: "Add size" }));
    fireEvent.change(screen.getByLabelText("Size"), { target: { value: "Large" } });
    fireEvent.change(screen.getByLabelText("Color name"), { target: { value: "42" } });

    expect(screen.getByLabelText("Hex value for 42").value).toBe("#111111");
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    expect(saveEcommerceItem.mock.calls[0][2].options[1].values[0]).toMatchObject({
      value_translations: { en: "42" },
      color_hex: "#111111",
    });
  });

  it("rejects combined size ranges and keeps size-color pairings explicit", async () => {
    renderEditor();
    nameProduct();
    addVariant({ name: "S/M", color: "Black", hex: "#111111", quantity: "4" });

    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    expect(await screen.findByText("Enter one size per row, for example S and M separately instead of S/M.")).toBeTruthy();
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

  it("explicitly converts legacy combined sizes while preserving colors and total inventory", async () => {
    const sizeOption = "11111111-1111-4111-8111-111111111111";
    const colorOption = "22222222-2222-4222-8222-222222222222";
    const sm = "33333333-3333-4333-8333-333333333333";
    const lxl = "44444444-4444-4444-8444-444444444444";
    const brown = "55555555-5555-4555-8555-555555555555";
    const product = {
      id: "product-1", slug: "belt", sku: "BELT", status: "draft", price: 46, currency: "ILS",
      translations: { en: { name: "Belt", description: "" }, ar: { name: "", description: "" } },
      attributes: [], images: [], tag_ids: [],
      options: [
        { id: sizeOption, code: "size", name_translations: { en: "Size" }, display_type: "text", values: [
          { id: sm, code: "sm", value_translations: { en: "S/M" }, active: true },
          { id: lxl, code: "lxl", value_translations: { en: "L/XL" }, active: true },
        ] },
        { id: colorOption, code: "color", name_translations: { en: "Color" }, display_type: "color", values: [
          { id: brown, code: "brown", value_translations: { en: "Brown" }, color_hex: "#70462E", active: true },
        ] },
      ],
      variants: [
        { id: "66666666-6666-4666-8666-666666666666", sku: "BELT-SM-BROWN", inventory_quantity: 5, low_stock_threshold: 2, track_inventory: true, allow_backorder: false, images: [], active: true, option_value_ids: [sm, brown] },
        { id: "77777777-7777-4777-8777-777777777777", sku: "BELT-LXL-BROWN", inventory_quantity: 4, low_stock_threshold: 2, track_inventory: true, allow_backorder: false, images: [], active: true, option_value_ids: [lxl, brown] },
      ],
    };
    fetchEcommerceCatalog.mockResolvedValue(catalog([product]));
    renderEditor({ initialCatalog: catalog([product]), productId: "product-1" });

    expect(await screen.findByDisplayValue("S/M")).toBeTruthy();
    expect(screen.getByDisplayValue("L/XL")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", {name:/S\/M: Split/}));
    await screen.findByDisplayValue("S");
    fireEvent.click(screen.getByRole("button", {name:/L\/XL: Split/}));
    for (const size of ["S", "M", "L", "XL"]) expect(await screen.findByDisplayValue(size)).toBeTruthy();
    expect(screen.queryByDisplayValue("S/M")).toBeNull();
    expect(screen.queryByDisplayValue("L/XL")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Save variants" }));

    await waitFor(() => expect(saveEcommerceProductVariants).toHaveBeenCalledOnce());
    const payload = saveEcommerceProductVariants.mock.calls[0][1];
    expect(payload.options[0].values.map((value) => value.value_translations.en)).toEqual(["S", "M", "L", "XL"]);
    expect(payload.variants).toHaveLength(4);
    expect(payload.variants.reduce((total, variant) => total + variant.inventory_quantity, 0)).toBe(9);
    expect(payload.variants.every((variant) => variant.option_value_ids.length === 2)).toBe(true);
  });

  it("localizes the redesigned inventory editor and preserves RTL direction", async () => {
    await appI18n.changeLanguage("ar");
    const { container } = renderEditor();
    expect(container.querySelector("form").getAttribute("dir")).toBe("rtl");
    expect(screen.getByRole("heading", { name: "الأنواع والمخزون" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "إضافة مقاس" })).toBeTruthy();
  });
});
