import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import "../../i18n";
import EcommerceLoyaltyPage from "./EcommerceLoyaltyPage";
import { fetchEcommerceCatalog, fetchEcommerceLoyalty, saveEcommerceLoyalty, fetchEcommerceSettings, saveEcommerceSettings } from "../../services/ecommerceApi";

vi.mock("../../services/ecommerceApi", () => ({ fetchEcommerceCatalog:vi.fn(), fetchEcommerceLoyalty:vi.fn(), saveEcommerceLoyalty:vi.fn(), fetchEcommerceSettings:vi.fn().mockResolvedValue({currency:"USD",currency_locked:false}), saveEcommerceSettings:vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); fetchEcommerceSettings.mockResolvedValue({currency:"USD",currency_locked:false}); });
it("keeps settings editable and loads the catalog when loyalty storage is unavailable", async () => {
  fetchEcommerceCatalog.mockResolvedValue({ products:[], commerce_currency:"USD" });
  fetchEcommerceLoyalty.mockRejectedValueOnce(new Error("Loyalty settings require database migration 097")).mockResolvedValueOnce({ currency:"USD" });
  render(<EcommerceLoyaltyPage />);
  await screen.findByLabelText("Currency");
  expect(screen.queryByRole("checkbox", {name:"Enable loyalty rewards"})).toBeNull();
  fireEvent.change(screen.getByLabelText("Points needed for a reward"), {target:{value:"200"}});
  expect(screen.getByLabelText("Points needed for a reward").value).toBe("200");
  expect(screen.getByRole("button", {name:"Save"}).disabled).toBe(true);
  expect(screen.queryByRole("button", {name:"Try again"})).toBeNull();
  expect(screen.getByLabelText("Currency").value).toBe("USD");
  const saveButton = screen.getByRole("button", {name:"Save"});
  expect(saveButton.closest("footer")).toBeTruthy();
  expect(screen.getByRole("button", {name:"Add discount condition"}).compareDocumentPosition(saveButton) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});

it("saves multiple products and separate normal and loyalty validity conditions", async () => {
  const products = ["a", "b"].map((id) => ({ id, status:"active", translations:{en:{name:`Product ${id}`}} }));
  fetchEcommerceCatalog.mockResolvedValue({ products });
  fetchEcommerceLoyalty.mockResolvedValue({ currency:"USD" });
  saveEcommerceLoyalty.mockImplementation(async (rule) => ({ rule }));
  render(<EcommerceLoyaltyPage />);
  await screen.findByLabelText("Currency");
  const first = within(screen.getByRole("region", {name:"Condition 1"}));
  fireEvent.click(first.getByText("Reward products"));
  fireEvent.click(first.getByRole("checkbox", {name:"Product a"}));
  fireEvent.click(first.getByRole("checkbox", {name:"Product b"}));
  fireEvent.change(first.getByLabelText("Discount (%)"), {target:{value:"15"}});
  fireEvent.change(first.getByLabelText("Reward validity"), {target:{value:"fixed_period"}});
  expect(first.getByLabelText("Validity days").value).toBe("30");
  fireEvent.click(screen.getByRole("button", {name:"Add discount condition"}));
  const second = within(screen.getByRole("region", {name:"Condition 2"}));
  expect(second.getByLabelText("Customer eligibility").value).toBe("normal");
  fireEvent.click(second.getByText("Reward products"));
  fireEvent.click(second.getByRole("checkbox", {name:"Product a"}));
  fireEvent.change(second.getByLabelText("Discount (%)"), {target:{value:"20"}});
  fireEvent.click(screen.getByRole("button", {name:"Save"}));
  await waitFor(() => expect(saveEcommerceLoyalty).toHaveBeenCalledWith(expect.objectContaining({
    enabled:true,
    discount_conditions:[
      {audience:"loyalty",product_ids:["a","b"],discount_basis_points:1500,validity_mode:"fixed_period",validity_days:30},
      {audience:"normal",product_ids:["a"],discount_basis_points:2000,validity_mode:"lifetime",validity_days:null},
    ],
  }), {scope:"authenticated"}));
});


it("selects search results without losing other selections and clears all selections", async () => {
  fetchEcommerceCatalog.mockResolvedValue({ products: ["a", "b", "c"].map(id => ({ id, status:"active", translations:{en:{name:`Product ${id}`}} })) });
  fetchEcommerceLoyalty.mockResolvedValue({ currency:"USD" });
  saveEcommerceLoyalty.mockImplementation(async rule => ({rule}));
  render(<EcommerceLoyaltyPage />);
  await screen.findByLabelText("Currency");
  fireEvent.click(screen.getByText("Reward products"));
  fireEvent.click(screen.getByRole("checkbox", {name:"Product a"}));
  fireEvent.change(screen.getByLabelText("Search products"), {target:{value:"Product b"}});
  fireEvent.click(screen.getByRole("button", {name:"Select all results"}));
  fireEvent.change(screen.getByLabelText("Search products"), {target:{value:""}});
  expect(screen.getByRole("checkbox", {name:"Product a"}).checked).toBe(true);
  expect(screen.getByRole("checkbox", {name:"Product b"}).checked).toBe(true);
  fireEvent.click(screen.getByRole("button", {name:"Select all", exact:true}));
  expect(screen.getAllByRole("checkbox").every(input => input.checked)).toBe(true);
  fireEvent.click(screen.getByRole("button", {name:"Clear selection"}));
  expect(screen.getAllByRole("checkbox").every(input => !input.checked)).toBe(true);
  fireEvent.click(screen.getByRole("button", {name:"Select all", exact:true}));
  fireEvent.click(screen.getByRole("button", {name:"Save"}));
  await waitFor(() => expect(saveEcommerceLoyalty).toHaveBeenCalledOnce());
  expect(saveEcommerceLoyalty.mock.calls[0][0].discount_conditions[0].product_ids).toEqual(["a", "b", "c"]);
});


it("offers supported currencies and persists the shared store currency", async () => {
  fetchEcommerceCatalog.mockResolvedValue({products:[]});
  fetchEcommerceLoyalty.mockResolvedValue({currency:"USD",rule:{reward_product_id:"a"}});
  saveEcommerceSettings.mockResolvedValue({currency:"JOD",currency_locked:false});
  saveEcommerceLoyalty.mockImplementation(async rule => ({rule}));
  render(<EcommerceLoyaltyPage />);
  const dropdown = await screen.findByLabelText("Currency");
  expect([...dropdown.options].map(option => option.value)).toEqual(["", "ILS", "JOD", "USD", "EUR"]);
  fireEvent.change(dropdown, {target:{value:"JOD"}});
  fireEvent.click(screen.getByRole("button", {name:"Save"}));
  await waitFor(() => expect(saveEcommerceSettings).toHaveBeenCalledWith("JOD"));
  await waitFor(() => expect(saveEcommerceLoyalty).toHaveBeenCalledOnce());
});

it("preserves the store currency lock", async () => {
  fetchEcommerceSettings.mockResolvedValue({currency:"ILS",currency_locked:true});
  fetchEcommerceCatalog.mockResolvedValue({products:[]});
  fetchEcommerceLoyalty.mockResolvedValue({currency:"USD"});
  render(<EcommerceLoyaltyPage />);
  const dropdown = await screen.findByLabelText("Currency");
  expect(dropdown.value).toBe("ILS");
  expect(dropdown.disabled).toBe(true);
});
