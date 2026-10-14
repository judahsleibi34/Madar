import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { buildMyPlanView } from "./MyPlanPage";
import MyPlanPage from "./MyPlanPage";
import { apiFetch } from "../../utils/apiClient";

const languageState = vi.hoisted(() => ({ language: "en" }));
vi.mock("../../i18n", () => ({
  useLanguage: () => ({ language: languageState.language, direction: languageState.language === "ar" ? "rtl" : "ltr" }),
}));
vi.mock("../../utils/apiClient", async (original) => ({ ...(await original()), apiFetch: vi.fn() }));
vi.mock("./utils/ecommerceAdminCache", () => ({
  getEcommerceCacheScope: () => "test", readEcommerceAdminCacheSnapshot: () => null,
  loadEcommerceAdminResource: (_scope, _key, loader) => loader(),
}));

afterEach(() => { cleanup(); vi.clearAllMocks(); languageState.language = "en"; });

describe("My Plan authoritative view", () => {
  it("uses catalog and backend entitlement data without static billing values", () => {
    const view = buildMyPlanView({
      catalog: { products: [{ id: "website", name: "Website" }] },
      currentPlan: {
        assigned_modules: ["website"], commercial_access_state: "active",
        paid_through: "2026-11-14T00:00:00Z", protection_contract_version: 145,
        pricing: { recurring_minor: 2000, price_groups: [{ price_book_id: "launch_2026", grandfathered: true }] },
      },
      usage: {
        storage: { used_bytes: 10, quota_bytes: 20 },
        workspace_seats: { used: 1, included_and_added: 1 },
        ai_tokens: { remaining_standard_tokens: 0 },
      },
      entitlements: {
        effective_modules: ["website"],
      },
      addons: {
        active: [],
        available: [{ id: "ocr", coming_soon: true }],
      },
    });

    expect(view.modules).toEqual([expect.objectContaining({ id: "website" })]);
    expect(view.assignedModules).toEqual(["website"]);
    expect(view.effectiveModules).toEqual(["website"]);
    expect(view.pricing.recurring_minor).toBe(2000);
    expect(view.protectionEligible).toBe(true);
    expect(view.protectionBooks).toEqual(["launch_2026"]);
    expect(view.schemaReady).toBe(true);
  });

  it("previews module changes through the server quote without applying them", async () => {
    const payloads = {
      "/billing/catalog": { catalog: { products: [
        { id: "forms", summary: "Forms" }, { id: "website", summary: "Website" }, { id: "ecommerce", summary: "Commerce" },
      ] } },
      "/billing/current-plan": { assigned_modules: ["website"], commercial_access_state: "active", paid_through: "2026-11-14T00:00:00Z", commercial_revision: 4, protection_contract_version: 145, pricing: { recurring_minor: 2000, currency: "USD", billing_interval: "month", price_groups: [{ price_book_id: "launch_2026", grandfathered: true }] } },
      "/billing/usage": {}, "/billing/entitlements": { entitlements: { effective_modules: ["website"] } }, "/billing/add-ons": { active: [] },
    };
    apiFetch.mockImplementation(async (url, options = {}) => {
      if (String(url).endsWith("/billing/module-quote")) return { ok: true, json: async () => ({ quote: { pricing: { recurring_minor: 3000, currency: "USD" } } }) };
      const key = Object.keys(payloads).find((path) => String(url).endsWith(path));
      expect(options.method || "GET").toBe("GET");
      return { ok: true, json: async () => payloads[key] };
    });
    render(<MemoryRouter><MyPlanPage user={{ id: 7 }} /></MemoryRouter>);
    await screen.findByRole("button", { name: /Preview price/ });
    fireEvent.click(screen.getByRole("button", { name: /Forms/ }));
    fireEvent.click(screen.getByRole("button", { name: /Preview price/ }));
    expect(await screen.findByText("$30")).toBeTruthy();
    const quoteCall = apiFetch.mock.calls.find(([url]) => String(url).endsWith("/billing/module-quote"));
    expect(JSON.parse(quoteCall[1].body).module_ids.sort()).toEqual(["forms", "website"]);
  });

  it("summarizes resolver protection flags without deriving eligibility", () => {
    const view = (groups) => buildMyPlanView({ currentPlan: { pricing: { price_groups: groups } } });
    expect(view([{ grandfathered: true, protection_valid_until: "2026-12-01T00:00:00Z" }]).protectionStatus).toBe("protected");
    expect(view([{ grandfathered: true, protection_valid_until: "2026-12-01T00:00:00Z" }]).protectedUntil).toBe("2026-12-01T00:00:00Z");
    expect(view([{ grandfathered: true }, { grandfathered: false, new_sales_active: true }]).protectionStatus).toBe("partial");
    expect(view([{ grandfathered: false, new_sales_active: true }]).protectionStatus).toBe("open");
    expect(view([{ grandfathered: false, new_sales_active: false }]).protectionStatus).toBe("none");
    expect(view([]).protectionStatus).toBe("none");
  });

  const mountWithQuote = (quoteResponse, plan = {}) => {
    const payloads = {
      "/billing/catalog": { catalog: { products: [
        { id: "forms", summary: "Forms" }, { id: "website", summary: "Website" }, { id: "ecommerce", summary: "Commerce" },
      ] } },
      "/billing/current-plan": { assigned_modules: ["website", "ecommerce"], commercial_access_state: "active", protection_contract_version: 145, pricing: { recurring_minor: 3000, currency: "USD", billing_interval: "month", price_groups: [{ price_book_id: "launch_2026", module_ids: ["ecommerce", "website"], recurring_minor: 3000, grandfathered: true }] }, ...plan },
      "/billing/usage": {}, "/billing/entitlements": { entitlements: { effective_modules: ["website", "ecommerce"] } }, "/billing/add-ons": { active: [] },
    };
    apiFetch.mockImplementation(async (url) => {
      if (String(url).endsWith("/billing/module-quote")) return quoteResponse;
      const key = Object.keys(payloads).find((path) => String(url).endsWith(path));
      return { ok: true, json: async () => payloads[key] };
    });
    return render(<MemoryRouter><MyPlanPage user={{ id: 7 }} /></MemoryRouter>);
  };

  it("shows the quoted price-book breakdown and warns that removal forfeits protection", async () => {
    mountWithQuote({ ok: true, json: async () => ({ quote: {
      removed_module_ids: ["ecommerce"],
      pricing: { module_ids: ["website"], recurring_minor: 2000, currency: "USD", price_groups: [{ price_book_id: "launch_2026", module_ids: ["website"], recurring_minor: 2000, grandfathered: true }] },
    } }) });
    await screen.findByRole("button", { name: /Preview price/ });
    fireEvent.click(screen.getByRole("button", { name: /Commerce/ }));
    fireEvent.click(screen.getByRole("button", { name: /Preview price/ }));
    expect(await screen.findByText(/Website · \$20 · Protected founding price/)).toBeTruthy();
    expect(screen.getByText(/Removing Commerce ends their founding-price protection/)).toBeTruthy();
  });

  it("maps quote failures to safe localized messages instead of backend text", async () => {
    mountWithQuote({ ok: false, json: async () => ({ detail: { code: "commercial_price_book_unavailable", message: "private backend text" } }) });
    await screen.findByRole("button", { name: /Preview price/ });
    fireEvent.click(screen.getByRole("button", { name: /Preview price/ }));
    expect((await screen.findByRole("alert")).textContent).toBe("No price book is currently open for this module selection.");
    expect(screen.queryByText("private backend text")).toBeNull();
  });

  it("renders Arabic access states and RTL without raw enum values", async () => {
    languageState.language = "ar";
    const { container } = mountWithQuote({ ok: true, json: async () => ({}) }, { commercial_access_state: "expired" });
    expect((await screen.findAllByText("منتهٍ")).length).toBeGreaterThan(0);
    expect(container.querySelector("main").getAttribute("dir")).toBe("rtl");
    expect(screen.queryByText("expired")).toBeNull();
    expect(screen.queryByText("Revision")).toBeNull();
  });
});
