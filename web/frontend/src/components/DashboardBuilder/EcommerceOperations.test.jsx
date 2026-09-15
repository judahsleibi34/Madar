import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import EcommerceDeliveryPage from "./EcommerceDeliveryPage";
import i18n from "../../i18n";
import EcommerceOrdersPage from "./EcommerceOrdersPage";
import {
  collectEcommerceOrderPayment,
  fetchEcommerceDeliveryAreas,
  fetchEcommerceOrder,
  fetchEcommerceOrders,
  saveEcommerceDeliveryAreas,
  transitionEcommerceOrder,
} from "../../services/ecommerceApi";

vi.mock("../../services/ecommerceApi", () => ({
  collectEcommerceOrderPayment: vi.fn(),
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

  it("renders tenant-filtered orders and sends date and service-area filters", async () => {
    fetchEcommerceDeliveryAreas.mockResolvedValue({ areas });
    fetchEcommerceOrders.mockResolvedValue({ orders: [{
      id: "order-1", order_number: "MD-1001", created_at: "2026-09-12T10:00:00Z",
      customer_name: "Buyer", customer_phone: "0590000000", service_area_name_en: "Ramallah",
      total: "25.00", currency: "ILS", status: "pending", payment_status: "unpaid", payment_method: "cash_on_delivery",
    }] });
    render(<MemoryRouter initialEntries={["/ecommerce/orders"]}><EcommerceOrdersPage /></MemoryRouter>);

    expect(await screen.findByText("MD-1001")).toBeTruthy();
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
