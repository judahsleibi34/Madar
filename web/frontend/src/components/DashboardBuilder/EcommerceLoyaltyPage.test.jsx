import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import "../../i18n";
import EcommerceLoyaltyPage from "./EcommerceLoyaltyPage";
import { fetchEcommerceCatalog, fetchEcommerceLoyalty, saveEcommerceLoyalty } from "../../services/ecommerceApi";

vi.mock("../../services/ecommerceApi", () => ({ fetchEcommerceCatalog:vi.fn(), fetchEcommerceLoyalty:vi.fn(), saveEcommerceLoyalty:vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });
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
