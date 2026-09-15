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
  const optionButton = screen.queryByRole("button", { name: "Add options" }) || screen.getByRole("button", { name: "Add another option" });
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
    expect(screen.getByText("This product has no options")).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    const payload = saveEcommerceItem.mock.calls[0][2];
    expect(payload.options).toEqual([]);
    expect(payload.variants).toEqual([]);
  });

  it("enters shirt values quickly, previews 12 combinations, and persists only four selected variants", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    saveEcommerceItem.mockResolvedValue({ id: "product-1" });
    renderEditor();

    fireEvent.change(await screen.findByLabelText("Name (English)"), { target: { value: "Shirt" } });
    addOption("Size", ["S", "M", "L", "XL"]);
    addOption("Color", ["Black", "White", "Blue"]);

    expect(screen.getByText("12 possible combinations")).toBeTruthy();
    expect(screen.queryByRole("table")).toBeNull();
    ["S / Black", "M / Black", "M / White", "XL / Blue"].forEach((name) => fireEvent.click(screen.getByRole("checkbox", { name })));
    fireEvent.click(screen.getByRole("button", { name: "Create selected variants (4)" }));

    expect(screen.getAllByRole("row")).toHaveLength(5);
    expect(screen.queryByText("S / White")).toBeTruthy();
    expect(screen.queryAllByText("S / White").some((node) => node.closest("tbody"))).toBe(false);
    fireEvent.change(screen.getAllByLabelText("Price override")[0], { target: { value: "27" } });
    fireEvent.change(screen.getAllByLabelText("Inventory")[0], { target: { value: "10" } });
    fireEvent.click(screen.getAllByText("Let customers order when sold out")[0]);
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    const payload = saveEcommerceItem.mock.calls[0][2];
    expect(payload.options.map((option) => option.code)).toEqual(["size", "color"]);
    expect(payload.options[0].values.map((value) => value.code)).toEqual(["s", "m", "l", "xl"]);
    expect(payload.variants).toHaveLength(4);
    expect(payload.variants[0]).toMatchObject({ price_override: 27, inventory_quantity: 10, allow_backorder: true });
    expect(payload.variants[1].price_override).toBeNull();
    const labels = payload.variants.map((variant) => variant.option_value_ids.map((id) => {
      const value = payload.options.flatMap((option) => option.values).find((entry) => entry.id === id);
      return value.value_translations.en;
    }).join(" / "));
    expect(labels).toEqual(["S / Black", "M / Black", "M / White", "XL / Blue"]);
  });

  it("prevents duplicate values and keeps required options obvious", async () => {
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    renderEditor();
    await screen.findByLabelText("Name (English)");
    addOption("Size", ["S"]);

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

  it("uses Arabic labels and RTL direction", async () => {
    await appI18n.changeLanguage("ar");
    fetchEcommerceCatalog.mockResolvedValue(catalog());
    const { container } = renderEditor();
    await screen.findByLabelText("الاسم بالإنجليزية");
    expect(container.querySelector("form").getAttribute("dir")).toBe("rtl");
    expect(screen.getByRole("heading", { name: "المواصفات" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "الخيارات والأنواع" })).toBeTruthy();
  });
});
