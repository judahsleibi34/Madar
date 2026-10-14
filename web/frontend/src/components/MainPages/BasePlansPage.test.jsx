import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import BasePlansPage from "./BasePlansPage";
import { apiFetch } from "../../utils/apiClient";

vi.mock("../../utils/apiClient", async (original) => ({
  ...(await original()), apiFetch: vi.fn(),
}));

const catalog = {
  currency: "USD",
  products: [
    { id: "forms", name: "Madar Forms", summary: "Forms", type: "core_module" },
    { id: "website", name: "Madar Website", summary: "Website", type: "core_module" },
    { id: "ecommerce", name: "Madar Commerce", summary: "Commerce", type: "core_module" },
    { id: "ai_website_assistant", name: "AI website assistant", type: "add_on", price_minor: 1000, currency: "USD", coming_soon: true },
  ],
  price_book: {
    id: "launch_2026_v2", version: "2026-10-14", currency: "USD", billing_interval: "month",
    standalone_minor: { forms: 1500, website: 2000, ecommerce: 2500 },
    bundle_minor: { 2: 3000, 3: 4000 }, sales_start_at: "2026-10-01T00:00:00Z", new_sales_active: true,
  },
};

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("launch pricing page", () => {
  it("renders all module and bundle amounts from the backend price book", async () => {
    apiFetch.mockResolvedValue({ ok: true, json: async () => ({ catalog }) });
    render(<MemoryRouter><BasePlansPage lang="en" /></MemoryRouter>);
    expect(await screen.findByText("$15")).toBeTruthy();
    expect(screen.getByText("$20")).toBeTruthy();
    expect(screen.getByText("$25")).toBeTruthy();
    expect(screen.getByText("$30")).toBeTruthy();
    expect(screen.getByText("$40")).toBeTruthy();
    expect(screen.getByText(/Reservations, scheduling/)).toBeTruthy();
  });

  it("shows a prepared but unopened book with its prices and a disabled action", async () => {
    const prepared = { ...catalog.price_book, sales_start_at: null, new_sales_active: false };
    apiFetch.mockResolvedValue({ ok: true, json: async () => ({ catalog: { ...catalog, price_book: prepared } }) });
    render(<MemoryRouter><BasePlansPage lang="en" /></MemoryRouter>);
    expect(await screen.findByText("Not yet open for new subscriptions")).toBeTruthy();
    expect(screen.getByText("$15")).toBeTruthy();
    expect(screen.getByText("$40")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Not available for new subscriptions" }).disabled).toBe(true);
  });

  it("states exact bundle savings derived from the backend book", async () => {
    apiFetch.mockResolvedValue({ ok: true, json: async () => ({ catalog }) });
    render(<MemoryRouter><BasePlansPage lang="en" /></MemoryRouter>);
    expect(await screen.findByText(/Save \$5–\$15 a month/)).toBeTruthy();
    expect(screen.getByText("Save $20 a month compared with buying them separately")).toBeTruthy();
  });

  it.each([
    ["backend failure", { ok: false, json: async () => ({ detail: "private" }) }, "We could not reach"],
    ["older API without a price book contract", { ok: true, json: async () => ({ catalog: { products: catalog.products } }) }, "has not been updated"],
    ["unreadable price book", { ok: true, json: async () => ({ catalog: { ...catalog, price_book: null } }) }, "could not be loaded"],
    ["malformed price book", { ok: true, json: async () => ({ catalog: { ...catalog, price_book: { ...catalog.price_book, bundle_minor: { 2: "30" } } } }) }, "incomplete"],
  ])("fails closed without prices for %s", async (_label, response, message) => {
    apiFetch.mockResolvedValue(response);
    render(<MemoryRouter><BasePlansPage lang="en" /></MemoryRouter>);
    expect((await screen.findByRole("alert")).textContent).toContain(message);
    expect(screen.queryByText("$15")).toBeNull();
    expect(screen.queryByText("private")).toBeNull();
  });

  it("fails closed when the network request rejects", async () => {
    apiFetch.mockRejectedValue(new TypeError("Failed to fetch"));
    render(<MemoryRouter><BasePlansPage lang="en" /></MemoryRouter>);
    expect((await screen.findByRole("alert")).textContent).toContain("We could not reach");
  });

  it("renders Arabic RTL copy and does not offer a closed founding book", async () => {
    apiFetch.mockResolvedValue({ ok: true, json: async () => ({ catalog: { ...catalog, price_book: { ...catalog.price_book, new_sales_active: false, sales_end_at: "2026-10-05T00:00:00Z" } } }) });
    const { container } = render(<MemoryRouter><BasePlansPage lang="ar" /></MemoryRouter>);
    expect(await screen.findByText("انتهى عرض التأسيس للاشتراكات الجديدة")).toBeTruthy();
    expect(container.querySelector("main").getAttribute("dir")).toBe("rtl");
    expect(screen.getByRole("button", { name: "غير متاح للاشتراكات الجديدة" }).disabled).toBe(true);
  });

  it("shows the AI assistant as a priced add-on for every module from the catalog", async () => {
    apiFetch.mockResolvedValue({ ok: true, json: async () => ({ catalog }) });
    render(<MemoryRouter><BasePlansPage lang="en" /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "AI assistant" })).toBeTruthy();
    expect(screen.getByText("+$10")).toBeTruthy();
    expect(screen.getByText("Coming soon")).toBeTruthy();
    expect(screen.getByText("Add to any plan")).toBeTruthy();
    const modules = screen.getByRole("list", { name: "Works with" });
    expect(modules.textContent).toBe("FormsWebsiteCommerce");
  });

  it("omits the assistant extra when the catalog does not price it", async () => {
    const products = catalog.products.filter((product) => product.id !== "ai_website_assistant");
    apiFetch.mockResolvedValue({ ok: true, json: async () => ({ catalog: { ...catalog, products } }) });
    render(<MemoryRouter><BasePlansPage lang="en" /></MemoryRouter>);
    expect(await screen.findByText("$25")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "AI assistant" })).toBeNull();
  });
});
