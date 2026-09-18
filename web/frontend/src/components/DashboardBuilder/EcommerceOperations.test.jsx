import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import EcommerceDeliveryPage from "./EcommerceDeliveryPage";
import i18n from "../../i18n";
import EcommerceOrdersPage from "./EcommerceOrdersPage";
import {
  collectEcommerceOrderPayment,
  createEcommerceDeliveryLocation,
  fetchEcommerceDeliveryAreas,
  fetchEcommerceOrder,
  fetchEcommerceOrders,
  saveEcommerceDeliveryAreas,
  transitionEcommerceOrder,
} from "../../services/ecommerceApi";

vi.mock("../../services/ecommerceApi", () => ({
  collectEcommerceOrderPayment: vi.fn(),
  createEcommerceDeliveryLocation: vi.fn(),
  fetchEcommerceDeliveryAreas: vi.fn(),
  fetchEcommerceOrder: vi.fn(),
  fetchEcommerceOrders: vi.fn(),
  saveEcommerceDeliveryAreas: vi.fn(),
  transitionEcommerceOrder: vi.fn(),
}));

const areas = [
  { id: "95000000-0000-0000-0000-000000000001", code: "ramallah", name_en: "Ramallah", name_ar: "رام الله", enabled: true },
  { id: "95000000-0000-0000-0000-000000000003", code: "nablus", name_en: "Nablus", name_ar: "نابلس", enabled: false },
];

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  i18n.changeLanguage("en");
});

describe("merchant ecommerce operations", () => {
  it("loads, searches, changes, and batch-saves delivery coverage", async () => {
    fetchEcommerceDeliveryAreas.mockResolvedValue({ areas });
    saveEcommerceDeliveryAreas.mockResolvedValue({ enabled_service_area_ids: areas.map((area) => area.id) });
    render(<EcommerceDeliveryPage />);

    expect(await screen.findByText("Ramallah")).toBeTruthy();
    expect(screen.getByText("1 enabled")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Search delivery areas"), { target: { value: "نابلس" } });
    expect(screen.queryByText("Ramallah")).toBeNull();
    fireEvent.click(screen.getByRole("checkbox", { name: /Nablus/ }));
    expect(screen.getByText("2 enabled")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Save delivery areas/ }));
    await waitFor(() => expect(saveEcommerceDeliveryAreas).toHaveBeenCalledWith(areas.map((area) => area.id), { scope: "authenticated" }));
  });

  it("creates a custom hierarchy and includes it in the next coverage save", async () => {
    fetchEcommerceDeliveryAreas.mockResolvedValue({ areas });
    const custom = { id: "custom-id", code: "custom-7-private", name_en: "Jordan / Amman / Downtown", name_ar: "Jordan / Amman / Downtown", enabled: false };
    createEcommerceDeliveryLocation.mockResolvedValue({ area: custom });
    saveEcommerceDeliveryAreas.mockResolvedValue({});
    render(<EcommerceDeliveryPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Add custom location" }));
    expect(screen.getByRole("dialog", { name: "Add custom location" })).toBeTruthy();
    fireEvent.change(screen.getByRole("textbox", { name: "Country", exact: true }), { target: { value: "Jordan" } });
    fireEvent.change(screen.getByLabelText("State / province / region (optional)"), { target: { value: "Amman" } });
    fireEvent.change(screen.getByLabelText("Country — Arabic (optional)"), { target: { value: "الأردن" } });
    fireEvent.change(screen.getByLabelText("State / province / region — Arabic (optional)"), { target: { value: "عمان" } });
    fireEvent.click(screen.getByRole("button", { name: "Add another location level" }));
    fireEvent.change(screen.getByLabelText("District / other level (optional)"), { target: { value: "Downtown" } });
    fireEvent.click(screen.getByRole("button", { name: "Add location", exact: true }));
    await waitFor(() => expect(createEcommerceDeliveryLocation).toHaveBeenCalledWith({ country: "Jordan", levels: ["Amman", "Downtown"], name_ar: "الأردن / عمان / Downtown" }, { scope: "authenticated" }));
    expect(await screen.findByText(custom.name_en)).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(saveEcommerceDeliveryAreas).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Save delivery areas/ }));
    await waitFor(() => expect(saveEcommerceDeliveryAreas).toHaveBeenCalledWith([areas[0].id, custom.id], { scope: "authenticated" }));
  });

  it("removes extra hierarchy fields while preserving the other values", async () => {
    fetchEcommerceDeliveryAreas.mockResolvedValue({ areas });
    render(<EcommerceDeliveryPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Add custom location" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Country", exact: true }), { target: { value: "Canada" } });
    const addLevel = screen.getByRole("button", { name: "Add another location level" });
    fireEvent.click(addLevel);
    fireEvent.click(addLevel);
    fireEvent.click(addLevel);
    expect(addLevel.disabled).toBe(true);
    const extras = screen.getAllByLabelText("District / other level (optional)");
    fireEvent.change(extras[1], { target: { value: "Keep me" } });
    fireEvent.click(screen.getByRole("button", { name: "Remove location level 3" }));
    expect(screen.getAllByLabelText("District / other level (optional)")).toHaveLength(2);
    expect(screen.getAllByLabelText("District / other level (optional)")[0].value).toBe("Keep me");
    expect(screen.getByRole("textbox", { name: "Country", exact: true }).value).toBe("Canada");
    expect(addLevel.disabled).toBe(false);
  });

  it("loads saved custom locations without exposing their internal ownership code", async () => {
    fetchEcommerceDeliveryAreas.mockResolvedValue({ areas: [{ id: "custom-id", code: "custom-7-private", name_en: "Canada / Ontario / Toronto", name_ar: "Canada / Ontario / Toronto", enabled: true }] });
    render(<EcommerceDeliveryPage />);
    expect(await screen.findByRole("checkbox", { name: "Canada / Ontario / Toronto" })).toHaveProperty("checked", true);
    expect(screen.queryByText("custom-7-private")).toBeNull();
  });

  it("keeps the custom-location form open when creation fails", async () => {
    fetchEcommerceDeliveryAreas.mockResolvedValue({ areas });
    createEcommerceDeliveryLocation.mockRejectedValue(new Error("SUPABASE_SERVICE_KEY=private-key; SQL relation internal_table failed"));
    render(<EcommerceDeliveryPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Add custom location" }));
    fireEvent.change(screen.getByRole("textbox", { name: "Country", exact: true }), { target: { value: "Jordan" } });
    fireEvent.click(screen.getByRole("button", { name: "Add location", exact: true }));
    expect((await screen.findByRole("alert")).textContent).toContain("Could not save delivery coverage");
    expect(document.body.textContent).not.toContain("SUPABASE_SERVICE_KEY");
    expect(document.body.textContent).not.toContain("internal_table");
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("renders tenant-filtered orders and sends date and service-area filters", async () => {
    fetchEcommerceDeliveryAreas.mockResolvedValue({ areas });
    fetchEcommerceOrders.mockResolvedValue({ orders: [{
      id: "order-1", order_number: "MD-1001", created_at: "2026-09-12T10:00:00Z",
      customer_name: "Buyer", customer_phone: "0590000000", service_area_name_en: "Ramallah",
      total: "25.00", currency: "ILS", status: "pending", payment_status: "unpaid", payment_method: "cash_on_delivery",
    }] });
    render(<MemoryRouter initialEntries={["/ecommerce/orders"]}><EcommerceOrdersPage /></MemoryRouter>);

    expect(await screen.findByText("MD-1001")).toBeTruthy();
    expect(screen.getByLabelText("Service area").closest("aside")).not.toBeNull();
    expect(screen.getByLabelText("Orders from date").closest("aside")).not.toBeNull();
    expect(screen.getByLabelText("Customer").closest("aside")).toBeNull();
    fireEvent.change(await screen.findByLabelText("Service area"), { target: { value: areas[0].id } });
    fireEvent.change(screen.getByLabelText("Orders from date"), { target: { value: "2026-09-01" } });
    await waitFor(() => expect(fetchEcommerceOrders).toHaveBeenCalledWith(expect.objectContaining({
      service_area_id: areas[0].id,
      date_from: "2026-09-01",
    }), { scope: "authenticated" }));
  });

  it("keeps order status and COD collection as separate commands", async () => {
    const detail = {
      order: { id: "order-1", order_number: "MD-1001", created_at: "2026-09-12T10:00:00Z", customer_name: "Buyer", customer_phone: "0590000000", customer_email: "buyer@example.com", service_area_name_en: "Ramallah", street: "Main", subtotal: "25", discount_total: "0", total: "25", currency: "ILS", status: "pending", payment_status: "unpaid" },
      items: [], status_history: [],
    };
    fetchEcommerceOrder.mockResolvedValue(detail);
    transitionEcommerceOrder.mockResolvedValue({ ...detail, order: { ...detail.order, status: "confirmed" } });
    collectEcommerceOrderPayment.mockResolvedValue({ ...detail, order: { ...detail.order, payment_status: "collected" } });
    render(<MemoryRouter initialEntries={["/ecommerce/orders/order-1"]}><EcommerceOrdersPage /></MemoryRouter>);

    expect(await screen.findByText("MD-1001")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirmed" }));
    await waitFor(() => expect(transitionEcommerceOrder).toHaveBeenCalledWith("order-1", "confirmed", ""));
    fireEvent.click(screen.getByRole("button", { name: /Mark COD collected/ }));
    await waitFor(() => expect(collectEcommerceOrderPayment).toHaveBeenCalledWith("order-1"));
  });
});
  it("localizes merchant delivery operations and uses RTL for Arabic", async () => {
    await i18n.changeLanguage("ar");
    fetchEcommerceDeliveryAreas.mockResolvedValue({ areas });

    render(<EcommerceDeliveryPage />);

    expect(await screen.findByRole("heading", { level: 1, name: "مناطق التوصيل" })).toBeTruthy();
    expect(screen.getByText("رام الله")).toBeTruthy();
    expect(screen.getByText("1 مفعّلة")).toBeTruthy();
    expect(screen.getByLabelText("البحث في مناطق التوصيل")).toBeTruthy();
    expect(document.querySelector(".ecommerce-operations-page").getAttribute("dir")).toBe("rtl");
  });


it("debounces Orders typing and ignores late results from an older search", async () => {
  fetchEcommerceDeliveryAreas.mockResolvedValue({areas:[]});
  let finishOld;
  fetchEcommerceOrders.mockImplementation(query => query.customer_name === "old"
    ? new Promise(resolve => { finishOld = resolve; }) : Promise.resolve({orders:[]}));
  render(<MemoryRouter initialEntries={["/ecommerce/orders"]}><EcommerceOrdersPage /></MemoryRouter>);
  await screen.findByText("No orders found");
  fetchEcommerceOrders.mockClear();
  fireEvent.change(screen.getByLabelText("Customer"), {target:{value:"o"}});
  fireEvent.change(screen.getByLabelText("Customer"), {target:{value:"ol"}});
  fireEvent.change(screen.getByLabelText("Customer"), {target:{value:"old"}});
  expect(fetchEcommerceOrders).not.toHaveBeenCalled();
  await waitFor(() => expect(fetchEcommerceOrders).toHaveBeenCalledOnce());
  expect(screen.getByRole("status", {name:/Loading orders/})).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Customer"), {target:{value:"new"}});
  await waitFor(() => expect(fetchEcommerceOrders).toHaveBeenCalledTimes(2));
  await screen.findByText("No orders found");
  finishOld({orders:[{id:"old",order_number:"STALE-ORDER",customer_name:"Old",total:0,currency:"USD"}]});
  await waitFor(() => expect(screen.queryByText("STALE-ORDER")).toBeNull());
});
