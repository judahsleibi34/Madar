import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import EcommercePage from "./EcommercePage";
import {
  deleteEcommerceItem,
  fetchEcommerceCatalog,
  saveEcommerceItem,
} from "../../services/ecommerceApi";

vi.mock("react-i18next", () => ({
  useTranslation: () => ({ i18n: { resolvedLanguage: "en" } }),
}));

vi.mock("../../services/ecommerceApi", () => ({
  fetchEcommerceCatalog: vi.fn(),
  saveEcommerceItem: vi.fn(),
  deleteEcommerceItem: vi.fn(),
}));

afterEach(cleanup);

beforeEach(() => {
  vi.clearAllMocks();
  fetchEcommerceCatalog.mockResolvedValue({ tags: [], categories: [], products: [] });
  saveEcommerceItem.mockResolvedValue({});
  deleteEcommerceItem.mockResolvedValue(null);
});

describe("EcommercePage", () => {
  it("creates a tag with English and Arabic translations", async () => {
    render(<EcommercePage section="tags" />);
    await screen.findByText("No tags yet");

    fireEvent.click(screen.getByRole("button", { name: "Add tag" }));
    const nameFields = screen.getAllByLabelText("Name");
    fireEvent.change(nameFields[0], { target: { value: "Summer" } });
    fireEvent.change(nameFields[1], { target: { value: "الصيف" } });
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

    rerender(<EcommercePage key="products" section="products" />);
    fireEvent.click(await screen.findByRole("button", { name: "Add product" }));
    expect(screen.getByText("Pricing")).toBeTruthy();
    expect(screen.getByText("Inventory")).toBeTruthy();
    expect(screen.getByText("Media, shipping, and tax")).toBeTruthy();
    expect(screen.getByText("SEO")).toBeTruthy();
  });
});
