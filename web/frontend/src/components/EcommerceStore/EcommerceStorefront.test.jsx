import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import EcommerceStorefront from "./EcommerceStorefront";
import i18n from "../../i18n";
import { fetchPublicEcommerceCatalog, fetchPublicEcommerceDeliveryAreas, fetchPublicEcommerceProduct, fetchPublicEcommerceProfile } from "../../services/ecommerceApi";
import { fetchPublicEcommerceOrderConfirmation } from "../../services/ecommerceApi";
import { recordPublicSiteVisit } from "../../services/siteVisitApi";

vi.mock("../../services/ecommerceApi", () => ({
  fetchPublicEcommerceCatalog: vi.fn(),
  fetchPublicEcommerceDeliveryAreas: vi.fn(),
  fetchPublicEcommerceOrderConfirmation: vi.fn(),
  fetchPublicEcommerceLoyalty: vi.fn(() => Promise.reject(new Error("guest"))),
  fetchPublicEcommerceDiscounts: vi.fn(() => Promise.resolve({ conditions:[] })),
  fetchPublicEcommerceProduct: vi.fn(),
  fetchPublicEcommerceProfile: vi.fn(),
  createPublicEcommerceOrder: vi.fn(),
  reconcilePublicEcommerceCart: vi.fn(),
}));

vi.mock("../../services/siteVisitApi", () => ({
  recordPublicSiteVisit: vi.fn(() => Promise.resolve({ success: true })),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  localStorage.clear();
  sessionStorage.clear();
  i18n.changeLanguage("en");
  document.documentElement.lang = "en";
  document.documentElement.removeAttribute("dir");
  document.body.removeAttribute("dir");


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
  it.each(["en", "ar"])("uses the %s store identity on the homepage and footer", async (locale) => {
    await i18n.changeLanguage(locale);
    const site = { brand: "English Store", description: "English description", brand_ar: "متجر مدار", description_ar: "وصف المتجر" };
    fetchPublicEcommerceCatalog.mockResolvedValue({ ...catalog, site });
    fetchPublicEcommerceProfile.mockResolvedValue({ site });
    render(<MemoryRouter initialEntries={["/store/demo"]}><Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes></MemoryRouter>);
    const name = locale === "ar" ? site.brand_ar : site.brand;
    const description = locale === "ar" ? site.description_ar : site.description;
    expect(await screen.findByRole("heading", { level: 1, name })).toBeTruthy();
    expect(screen.getAllByText(description).length).toBeGreaterThanOrEqual(2);
    expect(document.querySelector(".live-store").getAttribute("dir")).toBe(locale === "ar" ? "rtl" : "ltr");
  });

  it("falls back to English store identity when Arabic is blank", async () => {
    await i18n.changeLanguage("ar");
    const site = { brand: "English Store", description: "English description", brand_ar: "  ", description_ar: "" };
    fetchPublicEcommerceCatalog.mockResolvedValue({ ...catalog, site });
    fetchPublicEcommerceProfile.mockResolvedValue({ site });
    render(<MemoryRouter initialEntries={["/store/demo"]}><Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes></MemoryRouter>);
    expect(await screen.findByRole("heading", { level: 1, name: site.brand })).toBeTruthy();
    expect(screen.getAllByText(site.description).length).toBeGreaterThanOrEqual(2);
  });

  it("shows the cart subtotal and opens the checkout page", async () => {
    localStorage.setItem("madar-store-cart:demo", JSON.stringify([{
      id: "43b86c1a-fbf7-41d3-a58a-cbe07fc8459f",
      slug: "lavender-eye-pillow",
      name: "Lavender Linen Eye Pillow",
      quantity: 2,
      price: "28.00",
      currency: "USD",
      images: ["/form-flow-products/lavender-eye-pillow.jpg"],
    }]));
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
    fetchPublicEcommerceProfile.mockResolvedValue({ site: { brand: "Test Store" } });
    fetchPublicEcommerceDeliveryAreas.mockResolvedValue({
      areas: [{ id: "95000000-0000-0000-0000-000000000001", code: "ramallah", name_en: "Ramallah", name_ar: "رام الله" }],
    });

    render(
      <MemoryRouter initialEntries={["/store/demo"]}>
        <Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes>
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("button", { name: "Open cart, 2 items" }));
    expect(screen.getByText("Subtotal").parentElement.textContent).toContain("$56.00");
    fireEvent.click(screen.getByRole("link", { name: /Proceed to checkout/ }));

    expect(await screen.findByRole("heading", { level: 1, name: "Checkout" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Place order" })).toBeTruthy();
    expect(fetchPublicEcommerceProfile).toHaveBeenCalledWith("demo");
    expect(recordPublicSiteVisit).toHaveBeenCalledTimes(1);
    expect(recordPublicSiteVisit).toHaveBeenCalledWith("demo", "store");
  });

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
  it("defaults public English catalogs to LTR independently of the dashboard language", async () => {
    document.documentElement.lang = "ar";
    document.documentElement.dir = "rtl";
    document.body.dir = "rtl";
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);

    render(
      <MemoryRouter initialEntries={["/store/demo"]}>
        <Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes>
      </MemoryRouter>
    );

    await screen.findByRole("heading", { level: 1, name: "Test Store" });
    expect(document.querySelector(".live-store").getAttribute("dir")).toBe("ltr");
    expect(document.documentElement.getAttribute("dir")).toBe("ltr");
    expect(document.body.getAttribute("dir")).toBe("ltr");
    expect(fetchPublicEcommerceCatalog).toHaveBeenCalledWith(
      "demo",
      expect.objectContaining({ locale: "en" })
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

    expect(await screen.findByRole("heading", { level: 1, name: "Olive House" })).toBeTruthy();
    expect(screen.getAllByText("Made locally for thoughtful homes.")).toHaveLength(2);
    expect(screen.getByRole("heading", { name: "Home" })).toBeTruthy();
    expect(screen.getAllByText("Olive tray").length).toBeGreaterThan(0);
    expect(screen.getAllByAltText("Olive tray")).toHaveLength(2);
    expect(document.querySelector(".live-store").style.getPropertyValue("--store-accent")).toBe("#287a55");
    expect(screen.queryByRole("textbox")).toBeNull();
  });
  it("maps the published builder theme payload into every storefront color token", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue({
      ...catalog,
      site: {
        brand: "Form & Flow",
        theme: {
          accent: "#365849",
          accentDark: "#294438",
          background: "#f3efe7",
          surface: "#fffdf8",
          softSurface: "#e4ebe2",
          text: "#21312a",
          muted: "#68736d",
        },
      },
    });

    render(
      <MemoryRouter initialEntries={["/store/demo"]}>
        <Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes>
      </MemoryRouter>
    );

    await screen.findByRole("heading", { level: 1, name: "Form & Flow" });
    expect(document.querySelector(".live-store").classList.contains("is-form-flow")).toBe(false);
    const style = document.querySelector(".live-store").style;
    expect(style.getPropertyValue("--store-accent")).toBe("#365849");
    expect(style.getPropertyValue("--store-paper")).toBe("#f3efe7");
    expect(style.getPropertyValue("--store-soft")).toBe("#e4ebe2");
    expect(style.getPropertyValue("--store-night")).toBe("#294438");
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
    expect(await screen.findByRole("heading", { level: 1, name: "Standalone Store" })).toBeTruthy();
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
  it("loads visible product images first, lazy-loads the rest, and replaces failed images", async () => {
    const products = Array.from({ length: 4 }, (_, index) => ({
      id: `product-${index + 1}`,
      name: `Pilates product ${index + 1}`,
      slug: `pilates-product-${index + 1}`,
      price: "24.00",
      currency: "USD",
      in_stock: true,
      images: [`/form-flow-products/product-${index + 1}.jpg`],
    }));
    fetchPublicEcommerceCatalog.mockResolvedValue({
      site: { brand: "Form & Flow" },
      catalog: {
        categories: [],
        tags: [],
        products,
        pagination: { page: 1, pages: 1, total: 4, limit: 12 },
      },
    });

    render(
      <MemoryRouter initialEntries={["/store/demo/catalog"]}>
        <Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes>
      </MemoryRouter>
    );

    const first = await screen.findByAltText("Pilates product 1");
    expect(first.getAttribute("loading")).toBe("eager");
    expect(screen.getByAltText("Pilates product 3").getAttribute("loading")).toBe("eager");
    const fourth = screen.getByAltText("Pilates product 4");
    expect(fourth.getAttribute("loading")).toBe("lazy");
    expect(fourth.getAttribute("decoding")).toBe("async");

    fireEvent.error(fourth);
    expect(screen.getByLabelText("No product image")).toBeTruthy();
  });

  it("reloads a durable tokenized order confirmation with delivery snapshots", async () => {
    const token = "a".repeat(64);
    fetchPublicEcommerceOrderConfirmation.mockResolvedValue({
      site: { brand: "Test Store" },
      order: {
        id: "order-1", order_number: "MD-1001", created_at: "2026-09-12T10:00:00Z",
        customer_name: "Buyer", customer_phone: "0590000000", customer_email: "buyer@example.com",
        service_area_name_en: "Ramallah", street: "Main Street", building: "7", floor_apartment: "2A",
        subtotal: "25", discount_total: "0", total: "25", currency: "ILS",
        payment_status: "unpaid", status: "pending",
      },
      items: [{ id: "item-1", product_name: "Snapshot Product", sku: "SKU-1", quantity: 2, line_total: "25" }],
      status_history: [{ new_status: "pending", created_at: "2026-09-12T10:00:00Z" }],
    });

    render(
      <MemoryRouter initialEntries={[`/store/demo/confirmation/${token}`]}>
        <Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { level: 1, name: "MD-1001" })).toBeTruthy();
    expect(screen.getByText("Snapshot Product")).toBeTruthy();
    expect(screen.getByText(/Main Street/)).toBeTruthy();
    expect(fetchPublicEcommerceOrderConfirmation).toHaveBeenCalledWith("demo", token);
  });

  it("switches the live storefront between English LTR and Arabic RTL", async () => {
    fetchPublicEcommerceCatalog.mockImplementation((_subdomain, options) => Promise.resolve({
      site: { brand: "Bilingual Store" },
      catalog: {
        categories: [], tags: [],
        products: [{ id: "product-1", slug: "chair", name: options.locale === "ar" ? "كرسي" : "Chair", price: "20", currency: "ILS", in_stock: true, images: [] }],
        pagination: { page: 1, pages: 1, total: 1, limit: 12 },
      },
    }));

    render(
      <MemoryRouter initialEntries={["/store/demo/catalog"]}>
        <Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes>
      </MemoryRouter>
    );

    expect((await screen.findAllByText("Chair")).length).toBeGreaterThan(0);
    expect(document.querySelector(".live-store").getAttribute("dir")).toBe("ltr");
    fireEvent.click(screen.getByRole("button", { name: "العربية" }));

    expect((await screen.findAllByText("كرسي")).length).toBeGreaterThan(0);
    await waitFor(() => expect(document.querySelector(".live-store").getAttribute("dir")).toBe("rtl"));
    expect(document.documentElement.getAttribute("dir")).toBe("rtl");
    expect(document.body.getAttribute("dir")).toBe("rtl");
    expect(screen.getAllByRole("link", { name: "المنتجات" }).length).toBeGreaterThan(0);
    expect(fetchPublicEcommerceCatalog).toHaveBeenCalledWith("demo", expect.objectContaining({ locale: "ar" }));

    fireEvent.click(screen.getByRole("button", { name: "English" }));
    expect((await screen.findAllByText("Chair")).length).toBeGreaterThan(0);
    await waitFor(() => expect(document.querySelector(".live-store").getAttribute("dir")).toBe("ltr"));
    expect(document.documentElement.getAttribute("dir")).toBe("ltr");
  });

  it("localizes Arabic checkout and service areas with safe English fallback", async () => {
    await i18n.changeLanguage("ar");
    localStorage.setItem("madar-store-cart:demo", JSON.stringify([{
      id: "product-1", slug: "chair", name: "كرسي", quantity: 1, price: "20", currency: "ILS", images: [],
    }]));
    fetchPublicEcommerceProfile.mockResolvedValue({ site: { brand: "متجر" } });
    fetchPublicEcommerceDeliveryAreas.mockResolvedValue({ areas: [
      { id: "area-1", code: "ramallah", name_en: "Ramallah", name_ar: "رام الله" },
      { id: "area-2", code: "fallback", name_en: "English fallback", name_ar: "" },
    ] });

    render(
      <MemoryRouter initialEntries={["/store/demo/checkout"]}>
        <Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { level: 1, name: "إتمام الطلب" })).toBeTruthy();
    const area = screen.getByLabelText("منطقة التوصيل");
    await screen.findByRole("option", { name: "رام الله" });
    expect(area.textContent).toContain("رام الله");
    expect(area.textContent).toContain("English fallback");
    expect(screen.getByRole("button", { name: "إرسال الطلب" })).toBeTruthy();
    expect(document.querySelector(".live-store-checkout").closest(".live-store").getAttribute("dir")).toBe("rtl");
  });

  it("emits non-blocking PDP and cart events with stable commerce context", async () => {
    const received = [];
    const listener = (event) => received.push(event.detail);
    window.addEventListener("madar:commerce", listener);
    fetchPublicEcommerceProduct.mockResolvedValue({
      site: { brand: "Store" },
      product: { id: "product-1", slug: "chair", name: "Chair", price: "20", currency: "ILS", in_stock: true, images: [] },
      category: null, tags: [], attributes: [], options: [], variants: [],
    });

    render(
      <MemoryRouter initialEntries={["/store/demo/product/chair"]}>
        <Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { level: 1, name: "Chair" })).toBeTruthy();
    await waitFor(() => expect(received.filter((item) => item.event === "view_item")).toHaveLength(1));
    fireEvent.click(screen.getByRole("button", { name: "Add to cart" }));
    expect(screen.getByRole("status").textContent).toContain("Added to cart");
    fireEvent.click(screen.getByRole("button", { name: "Open cart, 1 item" }));
    fireEvent.click(await screen.findByRole("button", { name: "Remove Chair" }));
    expect(screen.getByRole("status").textContent).toContain("Item removed");

    await waitFor(() => {
      expect(received.map((item) => item.event)).toEqual(expect.arrayContaining(["view_item", "add_to_cart", "view_cart", "remove_from_cart"]));
    });
    expect(received.filter((item) => item.event === "view_item")).toHaveLength(1);
    expect(received.find((item) => item.event === "add_to_cart").payload).toMatchObject({
      product_id: "product-1", variant_id: null, quantity: 1, currency: "ILS", locale: "en",
    });
    window.removeEventListener("madar:commerce", listener);
  });

  it("renders localized announcement and configured featured order without changing price truth", async () => {
    const received = [];
    const listener = (event) => received.push(event.detail);
    window.addEventListener("madar:commerce", listener);
    fetchPublicEcommerceCatalog.mockResolvedValue({
      site: {
        brand: "Test Store",
        growth: {
          announcement_enabled: true,
          announcement_text_en: "Free local delivery this week",
          announcement_text_ar: "توصيل محلي مجاني هذا الأسبوع",
          announcement_link: "/store/demo/catalog",
          featured_product_ids: ["featured"],
          featured_category_ids: [],
        },
      },
      catalog: {
        categories: [], tags: [],
        products: [{ id: "latest", slug: "latest", name: "Latest", price: "5", currency: "USD", in_stock: true, images: [] }],
        featured_products: [{ id: "featured", slug: "featured", name: "Featured Soap", price: "12", compare_at_price: "15", currency: "USD", in_stock: true, images: [] }],
        featured_categories: [],
        pagination: { page: 1, pages: 1, total: 2, limit: 12 },
      },
    });

    render(<MemoryRouter initialEntries={["/store/demo"]}><Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes></MemoryRouter>);

    const announcement = await screen.findByText("Free local delivery this week");
    expect(announcement.closest(".live-store-announcement")).toBeTruthy();
    expect(screen.getAllByText("Featured Soap").length).toBeGreaterThan(0);
    expect(screen.queryByText("Latest")).toBeNull();
    expect(screen.getAllByText("$12.00").length).toBeGreaterThan(0);
    const announcementLink = screen.getByRole("link", { name: "Free local delivery this week" });
    announcementLink.addEventListener("click", (event) => event.preventDefault(), { once: true });
    fireEvent.click(announcementLink);
    await waitFor(() => expect(received.map((item) => item.event)).toEqual(expect.arrayContaining(["promotion_view", "promotion_click"])));
    window.removeEventListener("madar:commerce", listener);
  });
});

it("uses safe visible feedback when a public product request fails", async () => {
  fetchPublicEcommerceProduct.mockRejectedValue(new Error("SUPABASE_SERVICE_KEY=private-key; SQL internal_product failed"));
  render(<MemoryRouter initialEntries={["/store/demo/product/chair"]}><Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes></MemoryRouter>);
  expect((await screen.findByRole("alert")).textContent).toContain("Could not load the live store");
  expect(document.body.textContent).not.toContain("SUPABASE_SERVICE_KEY");
  expect(document.body.textContent).not.toContain("internal_product");
});

it("shows a safe cart error instead of success when browser storage rejects an add", async () => {
  fetchPublicEcommerceProduct.mockResolvedValue({ site: { brand: "Store" }, product: { id: "product-1", slug: "chair", name: "Chair", price: "20", currency: "ILS", in_stock: true, images: [] }, category: null, tags: [], attributes: [], options: [], variants: [] });
  render(<MemoryRouter initialEntries={["/store/demo/product/chair"]}><Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes></MemoryRouter>);
  await screen.findByRole("heading", { level: 1, name: "Chair" });
  const storage = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("internal_storage secret"); });
  try {
    fireEvent.click(screen.getByRole("button", { name: "Add to cart" }));
    expect(screen.getByRole("alert").textContent).toContain("Could not update your cart");
    expect(screen.queryByRole("status")).toBeNull();
    expect(document.body.textContent).not.toContain("internal_storage");
    expect(screen.getByRole("button", { name: "Open cart, 0 items" })).toBeTruthy();
  } finally { storage.mockRestore(); }
});

it("closes the mobile navigation after a page selection and Escape", async () => {
  fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
  fetchPublicEcommerceProfile.mockResolvedValue({ site: catalog.site });
  render(<MemoryRouter initialEntries={["/store/demo"]}><Routes><Route path="/store/:subdomain/*" element={<EcommerceStorefront />} /></Routes></MemoryRouter>);
  await screen.findByRole("heading", { level: 1, name: "Test Store" });
  const toggle = document.querySelector(".live-store-mobile-menu");
  fireEvent.click(toggle);
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  expect(toggle.getAttribute("aria-controls")).toBe("live-store-mobile-navigation");
  fireEvent.click(document.querySelector('#live-store-mobile-navigation a[href="/store/demo/categories"]'));
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(toggle);
  fireEvent.keyDown(document, { key: "Escape" });
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
});
