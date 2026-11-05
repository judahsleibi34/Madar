import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";

import BasePlansPage from "./BasePlansPage";
import { DASHBOARD_ROUTES } from "../../config/routes";
import { apiFetch } from "../../utils/apiClient";

vi.mock("../../utils/apiClient", async (original) => ({
  ...(await original()), apiFetch: vi.fn(),
}));

const products = [
  { id: "ai_website_assistant", type: "add_on", price_minor: 1000, currency: "USD", coming_soon: true },
];
const response = (catalog) => ({ ok: true, json: async () => ({ catalog }) });
const Location = () => <output aria-label="Current route">{useLocation().pathname}</output>;

async function renderPage(lang = "en") {
  let view;
  await act(async () => {
    view = render(<MemoryRouter><BasePlansPage lang={lang} /><Location /></MemoryRouter>);
  });
  return view;
}

function expectPublicPlans() {
  for (const [name, price] of [["Forms", "$15"], ["Website", "$20"], ["Commerce", "$20"], ["Advanced Statistics", "$30"], ["E-learning", "$30"]]) {
    const card = within(screen.getByRole("heading", { name, exact: true }).closest("article"));
    expect(card.getByText(price)).toBeTruthy();
    expect(card.getByText("Starting from")).toBeTruthy();
  }
  expect(within(screen.getByRole("heading", { name: "All five modules" }).closest("article")).getByText("$100")).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
  expect(screen.queryByText("Any two modules")).toBeNull();
  expect(screen.queryByText("All three modules")).toBeNull();
}

afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe("public pricing offers", () => {
  it.each([
    ["a null price book", response({ products, price_book: null })],
    ["an older catalog", response({ products })],
    ["an empty catalog", response(null)],
    ["a malformed product list", response({ products: {}, price_book: {} })],
    ["a failed billing response", { ok: false, json: async () => ({ detail: "private" }) }],
    ["unreadable JSON", { ok: true, json: async () => { throw Error("invalid_json"); } }],
  ])("keeps approved prices visible with %s", async (_label, result) => {
    apiFetch.mockResolvedValue(result);
    await renderPage();
    expectPublicPlans();
    expect(screen.queryByText("private")).toBeNull();
  });

  it("shows plans immediately while the catalog request is pending", async () => {
    apiFetch.mockReturnValue(new Promise(() => {}));
    await renderPage();
    expectPublicPlans();
    expect(screen.queryByText("Loading the current price book…")).toBeNull();
  });

  it("keeps plans visible when the network is offline", async () => {
    apiFetch.mockRejectedValue(new TypeError("Failed to fetch"));
    await renderPage();
    expectPublicPlans();
  });

  it("does not replace approved USD offers with another billing book or currency", async () => {
    const book = { new_sales_active: false, currency: "EUR", standalone_minor: { forms: 9900, website: 9900, ecommerce: 9900 } };
    apiFetch.mockResolvedValue(response({ products, price_book: book }));
    await renderPage();
    expectPublicPlans();
    expect(book.standalone_minor.ecommerce).toBe(9900);
    expect(screen.queryByText("€99")).toBeNull();
  });

  it("lists all five modules in the complete plan without the old bundle offers", async () => {
    apiFetch.mockResolvedValue(response({ products }));
    await renderPage();
    const card = within(screen.getByRole("heading", { name: "All five modules" }).closest("article"));
    for (const name of ["Forms", "Website", "Commerce", "Advanced Statistics", "E-learning"]) expect(card.getByText(name, { exact: true })).toBeTruthy();
    expect(card.queryByText("Starting from")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Bundle and save" })).toBeNull();
  });

  it("renders Arabic offers and RTL without a billing price book", async () => {
    apiFetch.mockResolvedValue(response({ price_book: null }));
    const { container } = await renderPage("ar");
    expect(screen.getByRole("heading", { name: "التعلّم الإلكتروني" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "الوحدات الخمس" })).toBeTruthy();
    expect(container.querySelector("main").getAttribute("dir")).toBe("rtl");
    expect(screen.getAllByText("ابتداءً من")).toHaveLength(5);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("adds the optional assistant only when the catalog provides a valid amount", async () => {
    apiFetch.mockResolvedValue(response({ products, price_book: null }));
    await renderPage();
    expect(screen.getByRole("heading", { name: "AI assistant" })).toBeTruthy();
    expect(screen.getByText("+$10")).toBeTruthy();
    expect(screen.getByRole("list", { name: "Works with" }).textContent).toBe("FormsWebsiteCommerce");
  });

  it("does not invent an assistant price when the catalog has none", async () => {
    apiFetch.mockResolvedValue(response({ products: [{ ...products[0], price_minor: null }] }));
    await renderPage();
    expectPublicPlans();
    expect(screen.queryByRole("heading", { name: "AI assistant" })).toBeNull();
  });

  it("only navigates to subscription management and never submits a purchase", async () => {
    apiFetch.mockResolvedValue(response({ price_book: null }));
    await renderPage();
    fireEvent.click(screen.getByRole("button", { name: "Manage subscription" }));
    expect(screen.getByLabelText("Current route").textContent).toBe(DASHBOARD_ROUTES.myPlan);
    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(apiFetch.mock.calls[0][1].method).toBe("GET");
  });
});
