import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import appI18n from "../../i18n";
import { fetchEcommerceCatalog, saveEcommerceItem } from "../../services/ecommerceApi";
import EcommerceProductEditorPage from "./EcommerceProductEditorPage";

vi.mock("../../services/ecommerceApi", () => ({
  fetchEcommerceCatalog: vi.fn(),
  saveEcommerceItem: vi.fn(),
  uploadEcommerceProductImage: vi.fn(),
}));

const catalog = (products = []) => ({
  commerce_currency: "ILS",
  products,
  categories: [{ id: "category-1", name: "Clothing" }],
  tags: [{ id: "tag-1", name: "Featured" }],
});

function renderEditor(path = "/ecommerce/products/new") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/ecommerce/products/new" element={<EcommerceProductEditorPage user={{ id: "user-1" }} />} />
        <Route path="/ecommerce/products/:productId/edit" element={<EcommerceProductEditorPage user={{ id: "user-1" }} />} />
        <Route path="/ecommerce/products" element={<p>Products</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

function addOption(name, values) {
  const optionButton = screen.getByRole("button", { name: "Add variant attribute" });
  fireEvent.click(optionButton);
  const nameInputs = screen.getAllByLabelText("English name");
  fireEvent.change(nameInputs.at(-1), { target: { value: name } });
  values.forEach((value) => {
    const addBtn = screen.getAllByRole("button", { name: /Add value|Add color/ }).at(-1);
    fireEvent.click(addBtn);
    const valueInput = screen.getByLabelText("Value");
    fireEvent.change(valueInput, { target: { value } });
    const submitBtns = screen.getAllByRole("button", { name: /Add value|Add color/ });
    fireEvent.click(submitBtns.at(-1));
  });
}

function addVariantRow() {
  fireEvent.click(screen.getByRole("button", { name: "Add variant" }));
}

afterEach(async () => {
  cleanup();
  vi.clearAllMocks();
  await appI18n.changeLanguage("en");
});

describe("merchant product options and variants editor", () => {
  it("keeps a simple product simple with no fake variant", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    saveEcommerceItem.mockResolvedValue({ id: "product-1" });
    renderEditor();

    fireEvent.change(await screen.findByLabelText("Name (English)"), { target: { value: "Simple mug" } });
    expect(screen.getByRole("button", { name: "Add variant attribute" })).toBeTruthy();
    expect(screen.queryByText("This is a simple product")).toBeNull();
    expect(screen.getByRole("heading", { name: "Inventory", exact: true })).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    const payload = saveEcommerceItem.mock.calls[0][2];
    expect(payload.options).toEqual([]);
    expect(payload.variants).toEqual([]);
  });

  it("adds variant rows with manual Size/Color values and persists them", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    saveEcommerceItem.mockResolvedValue({ id: "product-1" });
    renderEditor();

    fireEvent.change(await screen.findByLabelText("Name (English)"), { target: { value: "Shirt" } });
    addOption("Size", []);
    addOption("Color", []);
    expect(screen.queryByRole("heading", { name: "Inventory", exact: true })).toBeNull();
    fireEvent.change(screen.getAllByLabelText("Type").at(-1), { target: { value: "color" } });

    addVariantRow();
    const allInputs = screen.getAllByPlaceholderText("Size");
    const sizeInput = allInputs.at(-1);
    fireEvent.change(sizeInput, { target: { value: "S" } });
    const colorInputs = screen.getAllByPlaceholderText("Color");
    const colorInput = colorInputs.at(-1);
    fireEvent.change(colorInput, { target: { value: "Red" } });

    addVariantRow();
    const sizeInputs2 = screen.getAllByPlaceholderText("Size");
    fireEvent.change(sizeInputs2.at(-1), { target: { value: "S" } });
    const colorInputs2 = screen.getAllByPlaceholderText("Color");
    fireEvent.change(colorInputs2.at(-1), { target: { value: "Green" } });

    addVariantRow();
    const sizeInputs3 = screen.getAllByPlaceholderText("Size");
    fireEvent.change(sizeInputs3.at(-1), { target: { value: "M" } });
    const colorInputs3 = screen.getAllByPlaceholderText("Color");
    fireEvent.change(colorInputs3.at(-1), { target: { value: "Red" } });

    const quantityInputs = screen.getAllByLabelText(/quantity$/);
    fireEvent.change(quantityInputs[0], { target: { value: "10" } });
    fireEvent.change(quantityInputs[1], { target: { value: "5" } });
    fireEvent.change(quantityInputs[2], { target: { value: "8" } });

    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    const payload = saveEcommerceItem.mock.calls[0][2];
    expect(payload.options.map((option) => option.code)).toEqual(["size", "color"]);
    expect(payload.options[0].values.map((v) => v.value_translations.en)).toEqual(["S", "M"]);
    expect(payload.options[1].values.map((v) => v.value_translations.en)).toEqual(["Red", "Green"]);
    expect(payload.variants).toHaveLength(3);
    expect(payload.variants[0]).toMatchObject({ inventory_quantity: 10 });
    expect(payload.variants[1]).toMatchObject({ inventory_quantity: 5 });
    expect(payload.variants[2]).toMatchObject({ inventory_quantity: 8 });

    const labels = payload.variants.map((variant) => variant.option_value_ids.map((id) => {
      const value = payload.options.flatMap((option) => option.values).find((entry) => entry.id === id);
      return value.value_translations.en;
    }).join(" / "));
    expect(labels).toEqual(["S / Red", "S / Green", "M / Red"]);
  });

  it("preserves live color picker edits when adding another value", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    saveEcommerceItem.mockResolvedValue({ id: "product-1" });
    renderEditor();
    fireEvent.change(await screen.findByLabelText("Name (English)"), { target: { value: "Colored shirt" } });
    // Create Color option with both values via the addOption helper
    addOption("Color", ["Red", "Blue"]);
    // Change display type to color
    fireEvent.change(screen.getByLabelText("Type"), { target: { value: "color" } });
    // Expand to see color value rows
    fireEvent.click(screen.getByRole("button", { name: "Manage values" }));
    // Edit Red's hex
    fireEvent.click(screen.getAllByRole("button", { name: "Edit value" }).at(0));
    fireEvent.input(screen.getByLabelText("Color swatch"), { target: { value: "#e53935" } });
    // Edit Blue's hex (clicking Edit value for Blue opens its editor, closing Red's)
    fireEvent.click(screen.getAllByRole("button", { name: "Edit value" }).at(1));
    fireEvent.input(screen.getByLabelText("Color swatch"), { target: { value: "#1e88e5" } });
    // Click Red's edit again to verify hex is preserved
    fireEvent.click(screen.getAllByRole("button", { name: "Edit value" }).at(0));
    expect(screen.getByLabelText("Color swatch").value).toBe("#e53935");
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    expect(saveEcommerceItem.mock.calls[0][2].options[0].values.map((value) => value.color_hex)).toEqual(["#E53935", "#1E88E5"]);
  });

  it("prevents duplicate values and hides the redundant required-option control", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    renderEditor();
    await screen.findByLabelText("Name (English)");
    addOption("Size", ["S"]);

    expect(screen.queryByText("Advanced")).toBeNull();
    expect(screen.queryByRole("checkbox", { name: "Require a value for Size" })).toBeNull();
    // Open inline form and try to add a duplicate "s"
    fireEvent.click(screen.getAllByRole("button", { name: "Add value" }).at(-1));
    const valueInput = screen.getByLabelText("Value");
    fireEvent.change(valueInput, { target: { value: "s" } });
    const submitBtns = screen.getAllByRole("button", { name: "Add value" });
    fireEvent.click(submitBtns.at(-1));
    expect(screen.getByText("That value already exists in Size.")).toBeTruthy();
    // Expand the card to verify only one "S" chip exists
    fireEvent.click(screen.getByRole("button", { name: "Manage values" }));
    expect(screen.getAllByRole("button", { name: "S" })).toHaveLength(1);
  });

  it("allows incomplete option work to be saved as a draft", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    saveEcommerceItem.mockResolvedValue({ id: "product-1" });
    renderEditor();
    fireEvent.change(await screen.findByLabelText("Name (English)"), { target: { value: "Draft shirt" } });
    addOption("Size", ["S"]);
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
  });

  it("makes a manually added variant available by default when publishing", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    saveEcommerceItem.mockResolvedValue({ id: "product-1" });
    renderEditor();
    fireEvent.change(await screen.findByLabelText("Name (English)"), { target: { value: "Active shirt" } });
    addOption("Size", []);

    addVariantRow();
    const sizeInput = screen.getByPlaceholderText("Size");
    fireEvent.change(sizeInput, { target: { value: "S" } });

    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "active" } });
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    expect(saveEcommerceItem.mock.calls[0][2].variants).toHaveLength(1);
    expect(saveEcommerceItem.mock.calls[0][2].variants[0]).toMatchObject({ active: true, inventory_quantity: 0 });
  });

  it("archives a referenced value and preserves the existing variant identity and data", async () => {
    const valueId = "11111111-1111-4111-8111-111111111111";
    const optionId = "22222222-2222-4222-8222-222222222222";
    const variantId = "33333333-3333-4333-8333-333333333333";
    fetchEcommerceCatalog.mockResolvedValue(catalog([{
      id: "product-1", slug: "shirt", sku: null, status: "draft", price: 25, currency: "ILS",
      translations: { en: { name: "Shirt", description: "" }, ar: { name: "قميص", description: "" } },
      attributes: [], images: [], tag_ids: [], options: [{
        id: optionId, code: "size", name_translations: { en: "Size", ar: "المقاس" }, required: true, sort_order: 0,
        values: [{ id: valueId, code: "s", value_translations: { en: "S", ar: "صغير" }, sort_order: 0, active: true }],
      }],
      variants: [{
        id: variantId, sku: "SHIRT-S", barcode: "123", price_override: 27, compare_at_price_override: 30,
        track_inventory: true, inventory_quantity: 7, low_stock_threshold: 2, allow_backorder: true,
        images: [], active: true, option_value_ids: [valueId],
      }],
    }]));
    saveEcommerceItem.mockResolvedValue({ id: "product-1" });
    renderEditor("/ecommerce/products/product-1/edit");

    fireEvent.click(await screen.findByRole("button", { name: "Manage values" }));
    fireEvent.click(await screen.findByRole("button", { name: "Remove S" }));
    expect(screen.getByText(/used by an existing variant, so it was archived/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    const payload = saveEcommerceItem.mock.calls[0][2];
    expect(payload.options[0].values[0]).toMatchObject({ id: valueId, active: false });
    expect(payload.variants[0]).toMatchObject({
      id: variantId, sku: "SHIRT-S", barcode: "123", price_override: 27,
      compare_at_price_override: 30, inventory_quantity: 7, low_stock_threshold: 2,
      allow_backorder: true, images: [], option_value_ids: [valueId],
    });
  });

  it("allows adding a second variant row with existing option values", async () => {
    const sizeOption = "11111111-1111-4111-8111-111111111111";
    const colorOption = "22222222-2222-4222-8222-222222222222";
    const small = "33333333-3333-4333-8333-333333333333";
    const red = "44444444-4444-4444-8444-444444444444";
    const green = "55555555-5555-4555-8555-555555555555";
    const existingId = "66666666-6666-4666-8666-666666666666";
    fetchEcommerceCatalog.mockResolvedValue(catalog([{
      id: "product-1", slug: "shirt", sku: null, status: "draft", price: 20, currency: "ILS",
      translations: { en: { name: "Classic T-Shirt", description: "" }, ar: { name: "قميص كلاسيكي", description: "" } },
      attributes: [], images: [], tag_ids: [], options: [
        { id: sizeOption, code: "size", name_translations: { en: "Size", ar: "المقاس" }, required: true, display_type: "text", sort_order: 0, values: [{ id: small, code: "s", value_translations: { en: "S" }, sort_order: 0, active: true }] },
        { id: colorOption, code: "color", name_translations: { en: "Color", ar: "اللون" }, required: true, display_type: "color", sort_order: 1, values: [
          { id: red, code: "red", value_translations: { en: "Red", ar: "أحمر" }, color_hex: "#E53935", sort_order: 0, active: true },
          { id: green, code: "green", value_translations: { en: "Green", ar: "أخضر" }, color_hex: "#43A047", sort_order: 1, active: true },
        ] },
      ],
      variants: [{ id: existingId, sku: "TSH-S-RED", barcode: "123", price_override: null, compare_at_price_override: null, track_inventory: true, inventory_quantity: 10, low_stock_threshold: 2, allow_backorder: false, images: ["https://example.com/red.webp"], active: true, option_value_ids: [small, red] }],
    }]));
    saveEcommerceItem.mockResolvedValue({ id: "product-1" });
    renderEditor("/ecommerce/products/product-1/edit");

    const sizeInputs = await screen.findAllByPlaceholderText("Size");
    const existingSizeInput = sizeInputs[0];
    expect(existingSizeInput.value).toBe("S");

    addVariantRow();
    const newSizeInputs = screen.getAllByPlaceholderText("Size");
    const newSizeInput = newSizeInputs.at(-1);
    fireEvent.change(newSizeInput, { target: { value: "S" } });
    const colorInputs = screen.getAllByPlaceholderText("Color");
    const colorInput = colorInputs.at(-1);
    fireEvent.change(colorInput, { target: { value: "Green" } });

    const quantityInputs = screen.getAllByLabelText(/quantity$/);
    fireEvent.change(quantityInputs.at(-1), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    const variants = saveEcommerceItem.mock.calls[0][2].variants;
    expect(variants).toHaveLength(2);
    expect(variants[0]).toMatchObject({ id: existingId, sku: "TSH-S-RED", inventory_quantity: 10, images: ["https://example.com/red.webp"] });
    expect(variants[1]).toMatchObject({ inventory_quantity: 4, option_value_ids: [small, green] });
    expect(variants[1].id).not.toBe(existingId);
  });

  it("shows option columns in the variant row table for three dimensions", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    renderEditor();
    await screen.findByLabelText("Name (English)");
    addOption("Size", ["M"]);
    addOption("Color", ["Red", "Blue"]);
    addOption("Fit", ["Slim", "Regular"]);

    addVariantRow();
    const sizeInputs = screen.getAllByPlaceholderText("Size");
    fireEvent.change(sizeInputs.at(-1), { target: { value: "M" } });
    const colorInputs = screen.getAllByPlaceholderText("Color");
    fireEvent.change(colorInputs.at(-1), { target: { value: "Red" } });
    const fitInputs = screen.getAllByPlaceholderText("Fit");
    fireEvent.change(fitInputs.at(-1), { target: { value: "Slim" } });

    addVariantRow();
    const sizeInputs2 = screen.getAllByPlaceholderText("Size");
    fireEvent.change(sizeInputs2.at(-1), { target: { value: "M" } });
    const colorInputs2 = screen.getAllByPlaceholderText("Color");
    fireEvent.change(colorInputs2.at(-1), { target: { value: "Blue" } });
    const fitInputs2 = screen.getAllByPlaceholderText("Fit");
    fireEvent.change(fitInputs2.at(-1), { target: { value: "Regular" } });

    expect(screen.getAllByText("Size").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Color").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Fit").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("satisfies the Section 11 acceptance test for Size/Color attributes and manual variant inventory", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    saveEcommerceItem.mockResolvedValue({ id: "product-1" });
    const { container } = renderEditor();

    fireEvent.change(await screen.findByLabelText("Name (English)"), { target: { value: "Sneaker" } });

    // 1. Create Size (Text) with 42, 43, 44
    fireEvent.click(screen.getByRole("button", { name: "Add variant attribute" }));
    const enNameInputs = screen.getAllByLabelText("English name");
    fireEvent.change(enNameInputs.at(-1), { target: { value: "Size" } });

    fireEvent.click(screen.getAllByRole("button", { name: "Add value" }).at(-1));
    fireEvent.change(screen.getByLabelText("Value"), { target: { value: "42" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add value" }).at(-1));

    fireEvent.change(screen.getByLabelText("Value"), { target: { value: "43" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add value" }).at(-1));

    fireEvent.change(screen.getByLabelText("Value"), { target: { value: "44" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add value" }).at(-1));

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    // 2. Create Color (Color) with Red #FF0000, Green #00AA00, Black #000000
    fireEvent.click(screen.getByRole("button", { name: "Add variant attribute" }));
    const enNameInputs2 = screen.getAllByLabelText("English name");
    fireEvent.change(enNameInputs2.at(-1), { target: { value: "Color" } });
    const typeSelects = screen.getAllByLabelText("Type");
    fireEvent.change(typeSelects.at(-1), { target: { value: "color" } });

    fireEvent.click(screen.getAllByRole("button", { name: "Add color" }).at(-1));
    fireEvent.change(screen.getByLabelText("Value"), { target: { value: "Red" } });
    fireEvent.change(screen.getByLabelText("Hex"), { target: { value: "#FF0000" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add color" }).at(-1));

    fireEvent.change(screen.getByLabelText("Value"), { target: { value: "Green" } });
    fireEvent.change(screen.getByLabelText("Hex"), { target: { value: "#00AA00" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add color" }).at(-1));

    fireEvent.change(screen.getByLabelText("Value"), { target: { value: "Black" } });
    fireEvent.change(screen.getByLabelText("Hex"), { target: { value: "#000000" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add color" }).at(-1));

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    // 3. Manually create 4 variants:
    // - 42 + Red (qty 5)
    // - 42 + Green (qty 8)
    // - 43 + Red (qty 3)
    // - 44 + Black (qty 7)
    addVariantRow();
    fireEvent.change(screen.getAllByPlaceholderText("Size").at(-1), { target: { value: "42" } });
    fireEvent.change(screen.getAllByPlaceholderText("Color").at(-1), { target: { value: "Red" } });
    fireEvent.change(screen.getAllByLabelText(/quantity$/).at(-1), { target: { value: "5" } });

    addVariantRow();
    fireEvent.change(screen.getAllByPlaceholderText("Size").at(-1), { target: { value: "42" } });
    fireEvent.change(screen.getAllByPlaceholderText("Color").at(-1), { target: { value: "Green" } });
    fireEvent.change(screen.getAllByLabelText(/quantity$/).at(-1), { target: { value: "8" } });

    addVariantRow();
    fireEvent.change(screen.getAllByPlaceholderText("Size").at(-1), { target: { value: "43" } });
    fireEvent.change(screen.getAllByPlaceholderText("Color").at(-1), { target: { value: "Red" } });
    fireEvent.change(screen.getAllByLabelText(/quantity$/).at(-1), { target: { value: "3" } });

    addVariantRow();
    fireEvent.change(screen.getAllByPlaceholderText("Size").at(-1), { target: { value: "44" } });
    fireEvent.change(screen.getAllByPlaceholderText("Color").at(-1), { target: { value: "Black" } });
    fireEvent.change(screen.getAllByLabelText(/quantity$/).at(-1), { target: { value: "7" } });

    // Verify exactly 4 variants exist, not 9
    const rows = container.querySelectorAll(".ecommerce-variant-matrix-row");
    expect(rows).toHaveLength(4);

    // Verify independent quantities
    const qtyInputs = screen.getAllByLabelText(/quantity$/);
    expect(qtyInputs.map((input) => input.value)).toEqual(["5", "8", "3", "7"]);

    // Edit Red's hex value -> swatch updates in attribute editor
    const manageBtns = screen.getAllByRole("button", { name: "Manage values" });
    fireEvent.click(manageBtns.at(-1));
    const editBtns = screen.getAllByRole("button", { name: "Edit value" });
    fireEvent.click(editBtns[0]);
    fireEvent.change(screen.getByLabelText("Hex"), { target: { value: "#EE1111" } });
    fireEvent.click(screen.getByRole("button", { name: "Close value editor" }));

    const hexCodes = container.querySelectorAll(".ecommerce-editor-color-value-hex");
    expect(hexCodes[0].textContent).toBe("#EE1111");

    // Save product sends correct payload structure
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());

    const savedPayload = saveEcommerceItem.mock.calls[0][2];
    expect(savedPayload.options).toHaveLength(2);
    expect(savedPayload.options[0].values.map((v) => v.value_translations.en)).toEqual(["42", "43", "44"]);
    expect(savedPayload.options[1].values.map((v) => v.value_translations.en)).toEqual(["Red", "Green", "Black"]);
    expect(savedPayload.options[1].values[0].color_hex).toBe("#EE1111");
    expect(savedPayload.variants).toHaveLength(4);
    expect(savedPayload.variants.map((v) => v.inventory_quantity)).toEqual([5, 8, 3, 7]);
  });

  it("uses Arabic labels and RTL direction", async () => {
    await appI18n.changeLanguage("ar");
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    const { container } = renderEditor();
    await screen.findByLabelText("الاسم بالإنجليزية");
    expect(container.querySelector("form").getAttribute("dir")).toBe("rtl");
    expect(screen.getByRole("heading", { name: "المواصفات" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "خصائص الأنواع" })).toBeTruthy();
  });
});

