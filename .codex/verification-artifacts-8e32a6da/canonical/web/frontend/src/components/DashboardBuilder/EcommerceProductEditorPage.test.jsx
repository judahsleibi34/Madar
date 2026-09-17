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
  const valueInput = screen.getByLabelText(`New value for ${name}`);
  values.forEach((value) => {
    fireEvent.change(valueInput, { target: { value } });
    fireEvent.keyDown(valueInput, { key: "Enter" });
  });
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
    expect(screen.getByText("This is a simple product")).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    const payload = saveEcommerceItem.mock.calls[0][2];
    expect(payload.options).toEqual([]);
    expect(payload.variants).toEqual([]);
  });

  it("uses the Size by Color matrix and persists only the seven available T-shirt combinations", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    saveEcommerceItem.mockResolvedValue({ id: "product-1" });
    renderEditor();

    fireEvent.change(await screen.findByLabelText("Name (English)"), { target: { value: "Shirt" } });
    addOption("Size", ["S", "M", "L"]);
    addOption("Color", ["Red", "Green", "Blue"]);
    fireEvent.change(screen.getAllByLabelText("Type").at(-1), { target: { value: "color" } });
    [["Red", "#E53935"], ["Green", "#43A047"], ["Blue", "#1E88E5"]].forEach(([name, hex]) => {
      fireEvent.click(screen.getByRole("button", { name }));
      fireEvent.change(screen.getByLabelText("Color swatch"), { target: { value: hex } });
    });

    expect(screen.getByText("9 possible combinations")).toBeTruthy();
    const enabled = [["S", "Red", 10], ["S", "Green", 5], ["S", "Blue", 2], ["M", "Red", 8], ["M", "Green", 4], ["L", "Red", 3], ["L", "Blue", 6]];
    enabled.forEach(([size, color, quantity]) => {
      const label = `${size} / ${color}`;
      fireEvent.click(screen.getByRole("checkbox", { name: `${label} availability` }));
      fireEvent.change(screen.getByLabelText(`${label} quantity`), { target: { value: String(quantity) } });
    });
    fireEvent.change(screen.getByLabelText("S / Red price override"), { target: { value: "23" } });
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    const payload = saveEcommerceItem.mock.calls[0][2];
    expect(payload.options.map((option) => option.code)).toEqual(["size", "color"]);
    expect(payload.options[0].values.map((value) => value.code)).toEqual(["s", "m", "l"]);
    expect(payload.options[1]).toMatchObject({ display_type: "color" });
    expect(payload.options[1].values.map((value) => value.color_hex)).toEqual(["#E53935", "#43A047", "#1E88E5"]);
    expect(payload.variants).toHaveLength(7);
    expect(payload.variants[0]).toMatchObject({ price_override: 23, inventory_quantity: 10 });
    expect(payload.variants[1].price_override).toBeNull();
    const labels = payload.variants.map((variant) => variant.option_value_ids.map((id) => {
      const value = payload.options.flatMap((option) => option.values).find((entry) => entry.id === id);
      return value.value_translations.en;
    }).join(" / "));
    expect(labels).toEqual(enabled.map(([size, color]) => `${size} / ${color}`));
    expect(labels).not.toContain("M / Blue");
    expect(labels).not.toContain("L / Green");
  });

  it("prevents duplicate values and keeps required options obvious", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    renderEditor();
    await screen.findByLabelText("Name (English)");
    addOption("Size", ["S"]);

    fireEvent.click(screen.getByText("Advanced"));
    expect(screen.getByRole("checkbox", { name: "Require a value for Size" }).checked).toBe(true);
    const valueInput = screen.getByLabelText("New value for Size");
    fireEvent.change(valueInput, { target: { value: "s" } });
    fireEvent.keyDown(valueInput, { key: "Enter" });
    expect(screen.getByText("That value already exists in Size.")).toBeTruthy();
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

  it("blocks publishing an option product without a sellable variant", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    renderEditor();
    fireEvent.change(await screen.findByLabelText("Name (English)"), { target: { value: "Active shirt" } });
    addOption("Size", ["S"]);
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "active" } });
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    expect(screen.getByRole("alert").textContent).toBe("Create and activate at least one variant before publishing this product.");
    expect(saveEcommerceItem).not.toHaveBeenCalled();
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

  it("reloads the same variant and creates exactly one newly enabled combination", async () => {
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

    expect((await screen.findByLabelText("S / Red quantity")).value).toBe("10");
    expect(screen.getByLabelText("S / Green quantity").disabled).toBe(true);
    fireEvent.click(screen.getByRole("checkbox", { name: "S / Green availability" }));
    fireEvent.change(screen.getByLabelText("S / Green quantity"), { target: { value: "4" } });
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    const variants = saveEcommerceItem.mock.calls[0][2].variants;
    expect(variants).toHaveLength(2);
    expect(variants[0]).toMatchObject({ id: existingId, sku: "TSH-S-RED", inventory_quantity: 10, images: ["https://example.com/red.webp"] });
    expect(variants[1]).toMatchObject({ inventory_quantity: 4, option_value_ids: [small, green] });
    expect(variants[1].id).not.toBe(existingId);
  });

  it("groups three dimensions by the first attribute without a wide spreadsheet", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    renderEditor();
    await screen.findByLabelText("Name (English)");
    addOption("Size", ["M"]);
    addOption("Color", ["Red", "Blue"]);
    addOption("Fit", ["Slim", "Regular"]);
    expect(screen.getByRole("heading", { name: "Size: M" })).toBeTruthy();
    expect(screen.getByRole("checkbox", { name: "M / Red / Slim availability" })).toBeTruthy();
    expect(screen.getByRole("checkbox", { name: "M / Blue / Regular availability" })).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
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
