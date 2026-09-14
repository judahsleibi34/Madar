import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import EcommerceProductEditorPage from "./EcommerceProductEditorPage";
import { fetchEcommerceCatalog, saveEcommerceItem } from "../../services/ecommerceApi";

vi.mock("../../services/ecommerceApi", () => ({
  fetchEcommerceCatalog: vi.fn(),
  saveEcommerceItem: vi.fn(),
  uploadEcommerceProductImage: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("full-page ecommerce product editor", () => {
  it("saves merchant-defined localized attributes, options, values, and one explicit variant", async () => {
    fetchEcommerceCatalog.mockResolvedValue({
      commerce_currency: "ILS",
      products: [],
      categories: [{ id: "category-1", name: "Clothing" }],
      tags: [{ id: "tag-1", name: "Featured" }],
    });
    saveEcommerceItem.mockResolvedValue({ id: "product-1" });

    render(
      <MemoryRouter initialEntries={["/ecommerce/products/new"]}>
        <Routes>
          <Route path="/ecommerce/products/new" element={<EcommerceProductEditorPage user={{ id: "user-1" }} />} />
          <Route path="/ecommerce/products" element={<p>Products</p>} />
        </Routes>
      </MemoryRouter>,
    );

    fireEvent.change(await screen.findByLabelText("Name (English)"), { target: { value: "Shirt" } });
    fireEvent.click(screen.getByRole("button", { name: "Add attribute" }));
    fireEvent.change(screen.getByLabelText("Attribute name English"), { target: { value: "Material" } });
    fireEvent.change(screen.getByLabelText("Attribute value English"), { target: { value: "Cotton" } });
    fireEvent.change(screen.getByLabelText("Attribute name Arabic"), { target: { value: "الخامة" } });
    fireEvent.click(screen.getByRole("button", { name: "Add option" }));
    fireEvent.change(screen.getByPlaceholderText("Option name (EN)"), { target: { value: "Finish" } });
    fireEvent.change(screen.getByPlaceholderText("Option name (AR)"), { target: { value: "التشطيب" } });
    fireEvent.click(screen.getByRole("button", { name: "Add value" }));
    fireEvent.change(screen.getAllByPlaceholderText("Value (EN)").at(-1), { target: { value: "Matte" } });
    fireEvent.change(screen.getAllByPlaceholderText("Value (AR)").at(-1), { target: { value: "مطفي" } });
    fireEvent.click(screen.getByRole("button", { name: "Add explicit variant" }));
    fireEvent.change(screen.getByLabelText("Finish"), { target: { value: screen.getByRole("option", { name: "Matte" }).value } });
    fireEvent.change(screen.getByLabelText("Variant SKU"), { target: { value: "SHIRT-MATTE" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Save product" }).at(-1));

    await waitFor(() => expect(saveEcommerceItem).toHaveBeenCalledOnce());
    const [, , payload, options] = saveEcommerceItem.mock.calls[0];
    expect(options).toEqual({ scope: "user-user-1" });
    expect(payload.currency).toBe("ILS");
    expect(payload.attributes[0]).toMatchObject({
      name_translations: { en: "Material", ar: "الخامة" },
      value_translations: { en: "Cotton" },
      sort_order: 0,
    });
    expect(payload.options[0]).toMatchObject({
      code: "option-1",
      name_translations: { en: "Finish", ar: "التشطيب" },
      sort_order: 0,
    });
    expect(payload.options[0].values[0]).toMatchObject({ code: "value-1", value_translations: { en: "Matte", ar: "مطفي" } });
    expect(payload.variants[0]).toMatchObject({ sku: "SHIRT-MATTE", option_value_ids: [payload.options[0].values[0].id] });
  });
});
