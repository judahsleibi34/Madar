import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import EcommerceStorefront from "./EcommerceStorefront";
import { fetchPublicEcommerceCatalog, fetchPublicEcommerceProduct, fetchPublicEcommerceProfile } from "../../services/ecommerceApi";

vi.mock("../../services/ecommerceApi", () => ({
  fetchPublicEcommerceCatalog: vi.fn(),
  fetchPublicEcommerceProduct: vi.fn(),
  fetchPublicEcommerceProfile: vi.fn(),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
});

const catalog = {
  site: { brand: "Test Store" },
  catalog: {
    categories: [],
    tags: [],
    products: [],
    pagination: { page: 1, pages: 1, total: 0, limit: 12 },
  },
};

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="current query">{location.search}</output>;
}

describe("EcommerceStorefront", () => {
  it("supports catalog and store-wide search from URL state", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
    render(
      <MemoryRouter initialEntries={["/store/demo?search=original"]}>
        <Routes>
          <Route
            path="/store/:subdomain/*"
            element={
              <>
                <EcommerceStorefront />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    const search = await screen.findByRole("textbox");
    expect(screen.getByRole("heading", { level: 1, name: "Products" })).toBeTruthy();
    expect(search.value).toBe("original");
    fireEvent.change(search, { target: { value: "updated" } });
    fireEvent.submit(search.closest("form"));

    await waitFor(() => {
      expect(screen.getByLabelText("current query").textContent).toContain(
        "search=updated"
      );
    });
    expect(screen.getByRole("textbox").value).toBe("updated");
    const storeSearch = screen.getByRole("searchbox", { name: "Search store" });
    fireEvent.change(storeSearch, { target: { value: "chair" } });
    fireEvent.submit(storeSearch.closest("form"));
    await waitFor(() => {
      expect(screen.getByLabelText("current query").textContent).toContain("search=chair");
    });

    expect(fetchPublicEcommerceCatalog).toHaveBeenLastCalledWith(
      "demo",
      expect.objectContaining({ search: "chair" })
    );
  });
  it("shows all uploaded product images in the product gallery", async () => {
    fetchPublicEcommerceProduct.mockResolvedValue({
      site: { brand: "Test Store" },
      product: {
        id: "product-1",
        name: "Chair",
        slug: "chair",
        price: "20.00",
        currency: "ILS",
        in_stock: true,
        images: [
          "/uploads/tenant_7/builder_assets/0123456789abcdef0123456789abcdef.webp",
          "/uploads/tenant_7/builder_assets/fedcba9876543210fedcba9876543210.webp",
        ],
      },
      category: null,
      tags: [],
    });

    render(
      <MemoryRouter initialEntries={["/store/demo/product/chair"]}>
        <Routes>
          <Route path="/store/:subdomain/*" element={<EcommerceStorefront />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByAltText("Chair 1")).toBeTruthy();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1, name: "Chair" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Show product image 2" }));
    expect(await screen.findByAltText("Chair 2")).toBeTruthy();
  });
  it("renders a fixed landing layout with dynamic published store content", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue({
      site: {
        brand: "Olive House",
        description: "Made locally for thoughtful homes.",
        logo_url: "https://example.com/logo.webp",
        store_theme: {
          accent: "#287a55",
          background: "#fffdf8",
          surface: "#f3f0e8",
          text: "#17231d",
          muted: "#66736b",
        },
      },
      catalog: {
        categories: [{ id: "category-1", slug: "home", name: "Home", description: "Objects for everyday living", parent_id: null }],
        tags: [],
        products: [{
          id: "product-1",
          name: "Olive tray",
          slug: "olive-tray",
          category_id: "category-1",
          price: "35.00",
          currency: "ILS",
          in_stock: true,
          images: ["https://example.com/tray.webp"],
        }],
        pagination: { page: 1, pages: 1, total: 1, limit: 8 },
      },
    });

    render(
      <MemoryRouter initialEntries={["/store/demo"]}>
        <Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { level: 1, name: "Welcome to Olive House" })).toBeTruthy();
    expect(screen.getByRole("heading", { level: 2, name: "See what's new." })).toBeTruthy();
    expect(screen.getAllByText("Made locally for thoughtful homes.")).toHaveLength(2);
    expect(screen.getByRole("heading", { name: "Home" })).toBeTruthy();
    expect(screen.getAllByText("Olive tray").length).toBeGreaterThan(0);
    expect(screen.getAllByAltText("Olive tray")).toHaveLength(2);
    expect(document.querySelector(".live-store").style.getPropertyValue("--store-accent")).toBe("#287a55");
    expect(screen.queryByRole("textbox")).toBeNull();
  });
  it("provides native store pages without relying on a builder website", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue({
      site: {
        brand: "Standalone Store",
        contact_email: "hello@example.com",
        phone: "+970590000000",
      },
      catalog: {
        categories: [{ id: "category-1", slug: "gifts", name: "Gifts", description: "Thoughtful gifts", parent_id: null }],
        tags: [],
        products: [],
        pagination: { page: 1, pages: 1, total: 0, limit: 12 },
      },
    });
    fetchPublicEcommerceProfile.mockResolvedValue({
      site: {
        brand: "Standalone Store",
        contact_email: "hello@example.com",
        phone: "+970590000000",
      },
    });
    render(
      <MemoryRouter initialEntries={["/store/demo/categories"]}>
        <Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { level: 1, name: "Categories" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Gifts" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Home" }).getAttribute("href")).toBe("/store/demo");
    expect(screen.getAllByRole("link", { name: "Products" })[0].getAttribute("href")).toBe("/store/demo/catalog");

    fireEvent.click(screen.getByRole("link", { name: "Contact us" }));
    expect(await screen.findByRole("heading", { level: 1, name: "How can we help?" })).toBeTruthy();
    expect(screen.getAllByRole("link", { name: /hello@example.com/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /970590000000/i }).length).toBeGreaterThan(0);
    expect(fetchPublicEcommerceProfile).toHaveBeenCalledWith("demo");
    expect(fetchPublicEcommerceCatalog).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("link", { name: "Home" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Welcome to Standalone Store" })).toBeTruthy();
  });
  it.each([
    ["home", "/store/demo", "Loading home page", "is-landing"],
    ["products", "/store/demo/catalog", "Loading products page", "is-catalog"],
    ["categories", "/store/demo/categories", "Loading categories page", "is-categories"],
    ["contact", "/store/demo/contact", "Loading contact page", "is-contact"],
    ["product details", "/store/demo/product/chair", "Loading product details page", "is-product"],
  ])("shows a page-shaped skeleton while loading %s", (_name, route, label, className) => {
    const pending = new Promise(() => {});
    fetchPublicEcommerceCatalog.mockReturnValue(pending);
    fetchPublicEcommerceProduct.mockReturnValue(pending);

    render(
      <MemoryRouter initialEntries={[route]}>
        <Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes>
      </MemoryRouter>
    );

    const skeleton = screen.getByRole("status", { name: label });
    expect(skeleton.classList.contains(className)).toBe(true);
    expect(skeleton.querySelectorAll(".live-store-skeleton-block").length).toBeGreaterThan(1);
  });
});