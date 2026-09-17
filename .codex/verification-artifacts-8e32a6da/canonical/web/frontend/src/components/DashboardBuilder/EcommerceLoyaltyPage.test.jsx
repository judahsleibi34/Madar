import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import EcommerceLoyaltyPage from "./EcommerceLoyaltyPage";
import i18n from "../../i18n";
import { fetchEcommerceCatalog, fetchEcommerceLoyalty, saveEcommerceLoyalty } from "../../services/ecommerceApi";

vi.mock("../../services/ecommerceApi", () => ({
  fetchEcommerceCatalog: vi.fn(),
  fetchEcommerceLoyalty: vi.fn(),
  saveEcommerceLoyalty: vi.fn(),
}));

const product = { id: "11111111-1111-1111-1111-111111111111", status: "active", translations: { en: { name: "Coffee" }, ar: { name: "قهوة" } } };

afterEach(() => { cleanup(); vi.clearAllMocks(); i18n.changeLanguage("en"); });

describe("EcommerceLoyaltyPage", () => {
  it("saves a versioned fixed 10% loyalty rule", async () => {
    fetchEcommerceLoyalty.mockResolvedValue({ currency: "ILS", rule: null });
    fetchEcommerceCatalog.mockResolvedValue({ products: [product] });
    saveEcommerceLoyalty.mockResolvedValue({ rule: { enabled: true, earning_rate_basis_points: 500, threshold_points: 100, reward_product_id: product.id, reward_discount_basis_points: 1000, validity_mode: "lifetime", validity_days: null } });
    render(<EcommerceLoyaltyPage />);
    await screen.findByText("Customer loyalty");
    fireEvent.click(screen.getByLabelText("Enable loyalty rewards"));
    fireEvent.change(screen.getByLabelText("Reward product"), { target: { value: product.id } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(saveEcommerceLoyalty).toHaveBeenCalledWith(expect.objectContaining({
      enabled: true,
      earning_rate_basis_points: 500,
      reward_product_id: product.id,
      validity_mode: "lifetime",
      validity_days: null,
    }), { scope: "authenticated" }));
    expect(screen.getByDisplayValue("10%").readOnly).toBe(true);
    expect(screen.getByDisplayValue("ILS").readOnly).toBe(true);
  });

  it("renders Arabic labels in RTL with localized product names", async () => {
    await i18n.changeLanguage("ar");
    fetchEcommerceLoyalty.mockResolvedValue({ currency: "ILS", rule: null });
    fetchEcommerceCatalog.mockResolvedValue({ products: [product] });
    const { container } = render(<EcommerceLoyaltyPage />);
    await screen.findByText("ولاء العملاء");
    expect(container.querySelector("main")?.getAttribute("dir")).toBe("rtl");
    expect(screen.getByRole("option", { name: "قهوة" })).toBeTruthy();
  });
});
