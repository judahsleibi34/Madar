import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import EcommerceStorefront from "./EcommerceStorefront";
import i18n from "../../i18n";
import { normalizeWhatsAppNumber } from "../../utils/whatsapp";
import { createPublicEcommerceOrder, fetchPublicEcommerceCatalog, fetchPublicEcommerceDeliveryAreas, fetchPublicEcommerceLoyalty, fetchPublicEcommerceProduct, fetchPublicEcommerceProfile, fetchPublicStoreAccount, reconcilePublicEcommerceCart, registerPublicStoreAccount } from "../../services/ecommerceApi";
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
  fetchPublicStoreAccount: vi.fn(() => Promise.resolve({ logged_in: false, user: null })),
  loginPublicStoreAccount: vi.fn(),
  logoutPublicStoreAccount: vi.fn(),
  registerPublicStoreAccount: vi.fn(),
  createPublicEcommerceOrder: vi.fn(),
  reconcilePublicEcommerceCart: vi.fn(() => Promise.resolve({ valid: true, items: [] })),
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
  it("renders the configured responsive landing carousel and supports manual navigation", async () => {
    const carouselCatalog = {
      site: {
        brand: "Test Store",
        landing_page: {
          autoplay_enabled: true,
          interval_ms: 7000,
          slides: [
            { id: "slide-1", image_url: "/uploads/tenant_1/builder_assets/0123456789abcdef0123456789abcdef.png", title_en: "First campaign", subtitle_en: "First offer" },
            { id: "slide-2", image_url: "/uploads/tenant_1/builder_assets/abcdefabcdefabcdefabcdefabcdefab.webp", title_en: "Second campaign", subtitle_en: "Second offer" },
            { id: "slide-3", image_url: "/uploads/tenant_1/builder_assets/11111111111111111111111111111111.jpg", title_en: "Third campaign" },
          ],
        },
      },
      catalog: { categories: [], brands: [], tags: [], products: [], pagination: { page: 1, pages: 1, total: 0, limit: 12 } },
    };
    fetchPublicEcommerceCatalog.mockResolvedValue(carouselCatalog);
    fetchPublicEcommerceProfile.mockResolvedValue({ site: carouselCatalog.site });
    render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);

    expect(await screen.findByRole("heading", { name: "First campaign" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Shop now" })).toBeNull();
    const firstImage = document.querySelector(".live-store-hero-carousel-slide.is-active img");
    expect(firstImage?.getAttribute("src")).toContain("0123456789abcdef");
    expect(firstImage?.getAttribute("src")).toContain("?v=4&w=1440");
    expect(firstImage?.getAttribute("srcset")).toContain("&w=480 480w");
    expect(firstImage?.getAttribute("srcset")).toContain("&w=768 768w");
    expect(firstImage?.getAttribute("sizes")).toBe("100vw");
    expect(firstImage?.getAttribute("loading")).toBe("eager");
    expect(firstImage?.getAttribute("fetchpriority")).toBe("high");
    expect(document.querySelectorAll(".live-store-hero-carousel-slide img")).toHaveLength(2);
    expect(document.querySelectorAll(".live-store-hero-carousel-slide")[2].querySelector("img")).toBeNull();
    expect(document.querySelector(".live-store-hero-carousel-slide:not(.is-active) img")?.getAttribute("loading")).toBe("lazy");
    expect(document.querySelector(".live-store-hero-carousel-slide:not(.is-active) img")?.getAttribute("fetchpriority")).toBe("low");
    fireEvent.click(screen.getByRole("button", { name: "Next slide" }));
    expect(screen.getByRole("heading", { name: "Second campaign" })).toBeTruthy();
    expect(document.querySelector('.live-store-hero-carousel-slide.is-active img')?.getAttribute("src")).toContain("abcdefabcdef");
    expect(document.querySelector(".live-store-hero-carousel-slide.is-active img")?.getAttribute("loading")).toBe("eager");
    expect(document.querySelector(".live-store-hero-carousel-slide:not(.is-active) img")?.getAttribute("loading")).toBe("lazy");
    expect(document.querySelectorAll(".live-store-hero-carousel-slide")[0].querySelector("img")).toBeNull();
  });

  it("keeps internal draft preview in same-origin storage and rejects untrusted theme messages", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
    fetchPublicEcommerceProfile.mockResolvedValue({ site: { brand: "Test Store" } });
    localStorage.setItem("madar-online-store-theme-preview", JSON.stringify({ accent: "#224466" }));
    render(<MemoryRouter initialEntries={["/ecommerce-preview/demo?preview=draft"]}><Routes><Route path="/ecommerce-preview/:subdomain/*" element={<EcommerceStorefront subdomain="demo" previewBasePath="/ecommerce-preview/demo" />} /></Routes></MemoryRouter>);
    const storefront = await screen.findByRole("heading", { level: 1, name: "Test Store" });
    expect(storefront.closest(".live-store").style.getPropertyValue("--store-accent")).toBe("#224466");
    window.dispatchEvent(new MessageEvent("message", { origin: "https://untrusted.example", source: window, data: { type: "madar-online-store-theme-preview", theme: { accent: "#ff0000" } } }));
    expect(storefront.closest(".live-store").style.getPropertyValue("--store-accent")).toBe("#224466");
    window.dispatchEvent(new MessageEvent("message", { origin: window.location.origin, data: { type: "madar-online-store-theme-preview", theme: { accent: "#ff0000" } } }));
    expect(storefront.closest(".live-store").style.getPropertyValue("--store-accent")).toBe("#224466");
    window.dispatchEvent(new MessageEvent("message", { origin: window.location.origin, source: window, data: { type: "madar-online-store-theme-preview", theme: { accent: "#336699" } } }));
    await waitFor(() => expect(storefront.closest(".live-store").style.getPropertyValue("--store-accent")).toBe("#336699"));
    expect(document.head.querySelector('meta[name="robots"]')?.content).toContain("noindex");
  });

  it("renders a same-origin published preview from published data without draft overrides or visit tracking", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
    fetchPublicEcommerceProfile.mockResolvedValue({ site: { brand: "Test Store" } });
    localStorage.setItem("madar-online-store-theme-preview", JSON.stringify({ accent: "#224466" }));

    render(<MemoryRouter initialEntries={["/ecommerce-preview/demo"]}><Routes><Route path="/ecommerce-preview/:subdomain/*" element={<EcommerceStorefront subdomain="demo" previewBasePath="/ecommerce-preview/demo" />} /></Routes></MemoryRouter>);

    const storefront = await screen.findByRole("heading", { level: 1, name: "Test Store" });
    expect(storefront.closest(".live-store").style.getPropertyValue("--store-accent")).not.toBe("#224466");
    expect(recordPublicSiteVisit).not.toHaveBeenCalled();
  });

  it("hides points when the signed-in customer's tenant has no enabled loyalty rule", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
    fetchPublicEcommerceProfile.mockResolvedValue({ site: { brand: "Test Store" } });
    fetchPublicStoreAccount.mockResolvedValueOnce({ logged_in: true, user: { name: "Test Buyer", email: "buyer@example.com" } });
    fetchPublicEcommerceLoyalty.mockResolvedValueOnce({
      enabled: false,
      account: null,
      entitlements: [],
      transactions: [],
    });

    render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);

    await screen.findByRole("heading", { level: 1, name: "Test Store" });
    await waitFor(() => expect(fetchPublicEcommerceLoyalty).toHaveBeenCalledWith("demo"));
    expect(document.querySelector(".live-store-loyalty")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Open my account" }));
    expect(screen.queryByText("Your points")).toBeNull();
  });

  it("shows the customer avatar, points, and rewards inside the account panel", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
    fetchPublicEcommerceProfile.mockResolvedValue({ site: { brand: "Test Store" } });
    fetchPublicStoreAccount.mockResolvedValueOnce({ logged_in: true, user: { name: "Judah Sleibi", email: "judah@example.com", avatar: "" } });
    fetchPublicEcommerceLoyalty.mockResolvedValueOnce({
      enabled: true,
      account: { current_balance: 125 },
      entitlements: [{ id: "reward-1", status: "active" }],
      transactions: [],
    });

    render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);

    const accountButton = await screen.findByRole("button", { name: "Open my account" });
    expect(accountButton.textContent).toBe("JS");
    fireEvent.click(accountButton);
    expect(await screen.findByText("Your points")).toBeTruthy();
    expect(screen.getByText("125")).toBeTruthy();
    expect(screen.getByText("1 active reward")).toBeTruthy();
    fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("dialog", { name: "Customer account" })).toBeNull();
  });

  it("uses the customer avatar control instead of repeating the store logo", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue({
      ...catalog,
      site: { ...catalog.site, logo_url: "https://example.com/store-logo.webp" },
    });
    fetchPublicEcommerceProfile.mockResolvedValue({ site: { brand: "Test Store" } });

    render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);

    const trigger = await screen.findByRole("button", { name: "Sign in or register" });
    expect(trigger.querySelector(".live-store-account-store-logo")).toBeNull();
    expect(trigger.querySelector("svg")).toBeTruthy();
  });

  it("offers customer sign-in and registration from the header account control", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
    fetchPublicEcommerceProfile.mockResolvedValue({ site: { brand: "Test Store" } });

    render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);

    fireEvent.click(await screen.findByRole("button", { name: "Sign in or register" }));
    expect(screen.getByLabelText("Email")).toBeTruthy();
    expect(screen.getByLabelText("Password")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Continue with Google" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Register" }));
    expect(screen.getByLabelText("Full name")).toBeTruthy();
    expect(screen.getByLabelText("Confirm password")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Test Customer" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "customer@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password-one" } });
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "password-two" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Passwords do not match.");
    expect(registerPublicStoreAccount).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Create account" })).toBeTruthy();
  });

  it("positions the mobile account panel below the full header", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
    fetchPublicEcommerceProfile.mockResolvedValue({ site: { brand: "Test Store" } });
    const rect = (bottom) => ({
      bottom, height: bottom, left: 0, right: 393, top: 0, width: 393,
      x: 0, y: 0, toJSON: () => ({}),
    });
    const bounds = vi.spyOn(HTMLElement.prototype, "getBoundingClientRect")
      .mockImplementation(function getBounds() {
        if (this.classList?.contains("live-store-header")) return rect(140);
        if (this.classList?.contains("live-store-account-trigger")) return rect(60);
        return rect(0);
      });

    try {
      render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);
      fireEvent.click(await screen.findByRole("button", { name: "Sign in or register" }));
      const dialog = await screen.findByRole("dialog", { name: "Customer account" });
      await waitFor(() => expect(dialog.style.getPropertyValue("--store-account-popover-top")).toBe("148px"));
    } finally {
      bounds.mockRestore();
    }
  });

  it.each(["en", "ar"])("uses the %s store identity on the homepage and footer", async (locale) => {
    await i18n.changeLanguage(locale);
    const site = { brand: "English Store", description: "English description", brand_ar: "متجر مدار", description_ar: "وصف المتجر" };
    fetchPublicEcommerceCatalog.mockResolvedValue({ ...catalog, site });
    fetchPublicEcommerceProfile.mockResolvedValue({ site });
    render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);
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
    render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);
    expect(await screen.findByRole("heading", { level: 1, name: site.brand })).toBeTruthy();
    expect(screen.getAllByText(site.description).length).toBeGreaterThanOrEqual(2);
  });

  it("keeps social icons visible before their links are configured", async () => {
    const site = { brand: "Test Store" };
    fetchPublicEcommerceCatalog.mockResolvedValue({ ...catalog, site });
    fetchPublicEcommerceProfile.mockResolvedValue({ site });

    render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);

    await screen.findByRole("heading", { level: 1, name: "Test Store" });
    expect(document.querySelectorAll(".live-store-footer-social .is-disabled")).toHaveLength(4);
    expect(document.querySelector('[data-social-icon="facebook"]')).toBeTruthy();
  });

  it("shows configured social profiles in the footer", async () => {
    const site = {
      brand: "Test Store",
      social_links: { instagram: "https://instagram.com/test-store", snapchat: "https://snapchat.com/add/test-store" },
    };
    fetchPublicEcommerceCatalog.mockResolvedValue({ ...catalog, site });
    fetchPublicEcommerceProfile.mockResolvedValue({ site });

    render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);

    const instagram = await screen.findByRole("link", { name: "Instagram" });
    expect(instagram.getAttribute("href")).toBe(site.social_links.instagram);
    expect(instagram.getAttribute("target")).toBe("_blank");
    expect(instagram.querySelector('[data-social-icon="instagram"]')).toBeTruthy();
    expect(screen.getByRole("link", { name: "Snapchat" })).toBeTruthy();
    expect(document.querySelector(".live-store-footer").classList.contains("has-social-links")).toBe(true);
  });

  it("opens a WhatsApp chat using the phone number published in settings", async () => {
    const site = { brand: "Test Store", phone: "059 000 0000" };
    fetchPublicEcommerceCatalog.mockResolvedValue({ ...catalog, site });
    fetchPublicEcommerceProfile.mockResolvedValue({ site });

    render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);

    const link = await screen.findByRole("link", { name: "Chat with Test Store on WhatsApp" });
    const destination = new URL(link.href);
    expect(destination.origin).toBe("https://wa.me");
    expect(destination.pathname).toBe("/970590000000");
    expect(destination.searchParams.get("text")).toBe("Hello Test Store, I have a question about your store.");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toContain("noopener");
  });

  it("normalizes supported international WhatsApp numbers and rejects invalid values", () => {
    expect(normalizeWhatsAppNumber("+970 59 000 0000")).toBe("970590000000");
    expect(normalizeWhatsAppNumber("00972-50-123-4567")).toBe("972501234567");
    expect(normalizeWhatsAppNumber("0590000000")).toBe("970590000000");
    expect(normalizeWhatsAppNumber("not a phone")).toBe("");
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
      areas: [{
        id: "95000000-0000-0000-0000-000000000001",
        code: "ramallah",
        name_en: "Ramallah",
        name_ar: "Ramallah",
        delivery_fee: "6.50",
      }],
    });

    render(
      <MemoryRouter initialEntries={["/shop"]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("button", { name: "Open cart, 2 items" }));
    expect(screen.getByText("Subtotal").parentElement.textContent).toContain("$56.00");
    expect((await screen.findByText("Delivery fee")).parentElement.textContent).toContain("$6.50");
    expect(screen.getByText("Total").parentElement.textContent).toContain("$62.50");
    fireEvent.click(screen.getByRole("link", { name: /Proceed to checkout/ }));

    expect(await screen.findByRole("heading", { level: 1, name: "Checkout" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Place order" })).toBeTruthy();
    expect(screen.queryByLabelText("Street")).toBeNull();
    expect(screen.queryByLabelText("Building")).toBeNull();
    expect(screen.queryByLabelText("Floor / apartment")).toBeNull();
    expect(screen.queryByLabelText("Landmark / address description")).toBeNull();
    expect(screen.queryByLabelText("Delivery notes")).toBeNull();
    expect(await screen.findByRole("dialog", { name: "Sign in before ordering and earn points" })).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Close" }));
    fireEvent.click(screen.getByRole("button", { name: "Sign in to earn points" }));
    expect(await screen.findByRole("dialog", { name: "Customer account" })).toBeTruthy();
    expect(screen.getByText("Ramallah — $6.50")).toBeTruthy();
    expect(fetchPublicEcommerceProfile).toHaveBeenCalledWith("demo");
    expect(recordPublicSiteVisit).toHaveBeenCalledTimes(1);
    expect(recordPublicSiteVisit).toHaveBeenCalledWith("demo", "store");
  });

  it("prefills checkout contact details for an authenticated customer", async () => {
    localStorage.setItem("madar-store-cart:demo", JSON.stringify([{
      id: "43b86c1a-fbf7-41d3-a58a-cbe07fc8459f",
      slug: "linen-shirt",
      name: "Linen Shirt",
      quantity: 1,
      price: "42.00",
      currency: "USD",
      images: [],
    }]));
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
    fetchPublicEcommerceProfile.mockResolvedValue({ site: { brand: "Test Store" } });
    fetchPublicStoreAccount.mockResolvedValueOnce({
      logged_in: true,
      user: { name: "Test Buyer", email: "buyer@example.com", phone: "+970590000000" },
    });
    fetchPublicEcommerceLoyalty.mockResolvedValueOnce({ enabled: true, account: { current_balance: 10 }, entitlements: [], transactions: [] });
    fetchPublicEcommerceDeliveryAreas.mockResolvedValue({
      areas: [{ id: "95000000-0000-0000-0000-000000000001", code: "ramallah", name_en: "Ramallah", name_ar: "رام الله", delivery_fee: "6.50" }],
    });

    render(
      <MemoryRouter initialEntries={["/shop/checkout"]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByLabelText("Customer name").value).toBe("Test Buyer"));
    expect(screen.getByLabelText("Email").value).toBe("buyer@example.com");
    expect(screen.getByLabelText("Phone").value).toBe("+970590000000");
    expect(screen.getByText("Welcome back, Test Buyer. We filled in your saved contact details.")).toBeTruthy();
    expect(screen.queryByText("Sign in before ordering and earn points")).toBeNull();
  });

  it("blocks email domains without a dot before sending a checkout request", async () => {
    localStorage.setItem("madar-store-cart:demo", JSON.stringify([{
      id: "43b86c1a-fbf7-41d3-a58a-cbe07fc8459f",
      slug: "pleated-midi-skirt",
      name: "Pleated Midi Skirt",
      quantity: 1,
      price: "62.00",
      currency: "USD",
      images: [],
    }]));
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
    fetchPublicEcommerceProfile.mockResolvedValue({ site: { brand: "Test Store" } });
    fetchPublicEcommerceDeliveryAreas.mockResolvedValue({
      areas: [{
        id: "95000000-0000-0000-0000-000000000001",
        code: "ramallah",
        name_en: "Ramallah",
        name_ar: "Ramallah",
        delivery_fee: "25.00",
      }],
    });

    render(
      <MemoryRouter initialEntries={["/shop/checkout"]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
      </MemoryRouter>
    );

    await screen.findByRole("dialog", { name: "Sign in before ordering and earn points" });
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    fireEvent.change(await screen.findByLabelText("Customer name"), { target: { value: "Judah Sleibi" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "judahsleibi34@gmailcom" } });
    fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+970599203855" } });
    fireEvent.click(screen.getByRole("button", { name: "Place order" }));

    expect((await screen.findAllByRole("alert")).some((alert) => alert.textContent.includes("Please enter a valid email address."))).toBe(true);
    expect(document.activeElement).toBe(screen.getByLabelText("Email"));
    expect(reconcilePublicEcommerceCart).toHaveBeenCalledTimes(1);
    expect(createPublicEcommerceOrder).not.toHaveBeenCalled();
  });

  it("removes deleted products from a stale cart when checkout opens", async () => {
    localStorage.setItem("madar-store-cart:demo", JSON.stringify([
      { id: "deleted-product", slug: "old-product", name: "Old product", quantity: 2, price: "18.00", currency: "USD", images: [] },
      { id: "current-product", slug: "current-product", name: "Current product", quantity: 1, price: "80.00", currency: "USD", images: [] },
    ]));
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
    fetchPublicEcommerceProfile.mockResolvedValue({ site: { brand: "Test Store" } });
    fetchPublicEcommerceDeliveryAreas.mockResolvedValue({ areas: [] });
    reconcilePublicEcommerceCart.mockResolvedValue({
      valid: false,
      items: [
        { product_id: "deleted-product", variant_id: null, requested_quantity: 2, available: false, reason: "unavailable" },
        { product_id: "current-product", variant_id: null, requested_quantity: 1, available: true, reason: null, max_quantity: 99, name: "Current product", slug: "current-product", images: [], price: "80.00", currency: "USD" },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/shop/checkout"]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("Current product")).toBeTruthy();
    await waitFor(() => expect(screen.queryByText("Old product")).toBeNull());
    expect(JSON.parse(localStorage.getItem("madar-store-cart:demo"))).toEqual([
      expect.objectContaining({ id: "current-product", quantity: 1 }),
    ]);
    expect(await screen.findByText("Unavailable products were removed and reduced stock quantities were adjusted.")).toBeTruthy();
  });

  it("supports catalog and store-wide search from URL state", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue({
      ...catalog,
      catalog: {
        ...catalog.catalog,
        categories: [{ id: "women", slug: "women", name: "Women", parent_id: null }],
      },
    });
    render(
      <MemoryRouter initialEntries={["/shop?search=original"]}>
        <Routes>
          <Route
            path="/shop/*"
            element={
              <>
                <EcommerceStorefront subdomain="demo" />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>
    );

    const search = await screen.findByRole("textbox");
    const poweredByLink = screen.getByRole("link", { name: "Powered by Madar Portal" });
    expect(poweredByLink.getAttribute("href")).toBe("https://madarportal.com/");
    expect(screen.getByRole("heading", { level: 1, name: "Products" })).toBeTruthy();
    expect(screen.queryByText("Showing 0 results")).toBeNull();
    expect(search.value).toBe("original");
    fireEvent.change(search, { target: { value: "updated" } });

    await waitFor(() => {
      expect(screen.getByLabelText("current query").textContent).toContain(
        "search=updated"
      );
    });
    expect(screen.getByRole("textbox").value).toBe("updated");
    fireEvent.click(screen.getByRole("button", { name: "Women" }));
    await waitFor(() => expect(screen.getByLabelText("current query").textContent).toContain("category=women"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "" } });
    await waitFor(() => {
      const currentQuery = screen.getByLabelText("current query").textContent;
      expect(currentQuery).not.toContain("search=");
      expect(currentQuery).toContain("category=women");
    });
    expect(fetchPublicEcommerceCatalog).toHaveBeenLastCalledWith(
      "demo",
      expect.objectContaining({ search: "", category: "women" })
    );
    fireEvent.click(screen.getByRole("button", { name: "Women" }));
    await waitFor(() => expect(screen.getByLabelText("current query").textContent).not.toContain("category=women"));
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

  it("updates URL-backed price filters from the dual range slider", async () => {
    fetchPublicEcommerceCatalog.mockResolvedValue({
      ...catalog,
      catalog: {
        ...catalog.catalog,
        price_bounds: { min: "5", max: "100", currency: "USD" },
      },
    });
    render(
      <MemoryRouter initialEntries={["/shop/catalog?min_price=10&max_price=80"]}>
        <Routes>
          <Route path="/shop/*" element={<><EcommerceStorefront subdomain="demo" /><LocationProbe /></>} />
        </Routes>
      </MemoryRouter>
    );

    const minimum = await screen.findByRole("slider", { name: "Minimum" });
    const maximum = screen.getByRole("slider", { name: "Maximum" });
    expect(minimum.value).toBe("10");
    expect(maximum.value).toBe("80");

    fireEvent.change(minimum, { target: { value: "25" } });

    await waitFor(() => {
      expect(screen.getByLabelText("current query").textContent).toContain("min_price=25");
    });
    expect(fetchPublicEcommerceCatalog).toHaveBeenLastCalledWith(
      "demo",
      expect.objectContaining({ min_price: "25", max_price: "80" })
    );
  });

  it("defaults public English catalogs to LTR independently of the dashboard language", async () => {
    document.documentElement.lang = "ar";
    document.documentElement.dir = "rtl";
    document.body.dir = "rtl";
    fetchPublicEcommerceCatalog.mockResolvedValue(catalog);

    render(
      <MemoryRouter initialEntries={["/shop"]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
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
        description: "Built for everyday use.",
        images: [
          "/uploads/tenant_7/builder_assets/0123456789abcdef0123456789abcdef.webp",
          "/uploads/tenant_7/builder_assets/fedcba9876543210fedcba9876543210.webp",
        ],
      },
      category: null,
      tags: [{ id: "tag-1", name: "Responsibly made" }],
    });

    render(
      <MemoryRouter initialEntries={["/shop/product/chair"]}>
        <Routes>
          <Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByAltText("Chair 1")).toBeTruthy();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1, name: "Chair" })).toBeTruthy();
    const detailVisual = document.querySelector(".live-store-detail-visual");
    expect(detailVisual?.querySelector(":scope > .live-store-detail-gallery")).toBeTruthy();
    expect(detailVisual?.querySelector(":scope > .live-store-detail-about .live-store-detail-description")?.textContent).toBe("Built for everyday use.");
    expect(detailVisual?.querySelector(":scope > .live-store-detail-about .live-store-detail-tags")?.textContent).toContain("Responsibly made");
    expect(document.querySelector(".live-store-detail-copy .live-store-detail-description")).toBeNull();
    const zoomButton = screen.getByRole("button", { name: "Open enlarged product image" });
    fireEvent.mouseEnter(zoomButton);
    expect(zoomButton.classList.contains("is-hovered")).toBe(true);
    fireEvent.click(zoomButton);
    expect(screen.getByRole("dialog", { name: "Enlarged product image" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Close enlarged product image" }));
    expect(screen.queryByRole("dialog", { name: "Enlarged product image" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Show product image 2" }));
    expect(await screen.findByAltText("Chair 2")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Open enlarged product image" }).classList.contains("is-hovered")).toBe(false);
  });
  it("adds several units of one selected variant as one cart line", async () => {
    fetchPublicEcommerceProduct.mockResolvedValue({
      site: { brand: "Test Store" },
      product: { id: "product-1", name: "Chair", slug: "chair", price: "20.00", currency: "ILS", in_stock: true, images: [] },
      category: null,
      tags: [],
      attributes: [],
      options: [{
        id: "color",
        code: "color",
        name: "Color",
        required: true,
        display_type: "color",
        values: [
          { id: "black", code: "black", value: "Black", color_hex: "#000000" },
          { id: "sand", code: "sand", value: "Sand", color_hex: "#d8c7a5" },
        ],
      }],
      variants: [
        { id: "variant-black", sku: "CHAIR-BLACK", price: "20.00", in_stock: true, active: true, track_inventory: true, inventory_quantity: 4, allow_backorder: false, option_value_ids: ["black"], images: [] },
        { id: "variant-sand", sku: "CHAIR-SAND", price: "20.00", in_stock: true, active: true, track_inventory: true, inventory_quantity: 18, allow_backorder: false, option_value_ids: ["sand"], images: [] },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/shop/product/chair"]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("radio", { name: "Sand" }));
    expect(screen.getByText("18 items available")).toBeTruthy();
    const quantity = screen.getByRole("spinbutton", { name: "Quantity" });
    fireEvent.change(quantity, { target: { value: "10" } });
    expect(quantity.value).toBe("10");
    fireEvent.click(screen.getByRole("button", { name: "Add to cart" }));

    const saved = JSON.parse(localStorage.getItem("madar-store-cart:demo"));
    expect(saved).toHaveLength(1);
    expect(saved[0]).toMatchObject({ variant_id: "variant-sand", quantity: 10 });
    expect(saved[0].selected_options[0].value).toBe("Sand");
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
        categories: [
          { id: "category-1", slug: "home", name: "Home", description: "Objects for everyday living", image_url: "https://example.com/home.webp", parent_id: null },
          { id: "category-2", slug: "studio", name: "Studio", description: "Tools for creative rooms", image_url: null, parent_id: null },
        ],
        brands: [
          { id: "brand-1", slug: "olive", name: "Olive Studio", image_url: "https://example.com/olive.webp" },
          { id: "brand-2", slug: "cedar", name: "Cedar Works", image_url: null },
        ],
        tags: [],
        products: [{
          id: "product-1",
          name: "Olive tray",
          slug: "olive-tray",
          category_id: "category-1",
          price: "35.00",
          currency: "ILS",
          in_stock: true,
          has_variants: true,
          variant_options: [
            { id: "color", name: "Color", display_type: "color", values: ["Black", "Sand"] },
            { id: "size", name: "Size", display_type: "text", values: ["36", "37", "38"] },
          ],
          images: ["https://example.com/tray.webp"],
        }],
        pagination: { page: 1, pages: 1, total: 1, limit: 8 },
      },
    });

    render(
      <MemoryRouter initialEntries={["/shop"]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { level: 1, name: "Olive House" })).toBeTruthy();
    expect(screen.getAllByText("Made locally for thoughtful homes.")).toHaveLength(2);
    expect(document.querySelector(".live-store-footer-brand img")?.getAttribute("src")).toContain("logo.webp");
    expect(screen.getByRole("heading", { name: "Home" })).toBeTruthy();
    expect(document.querySelectorAll(".live-store-category-carousel")).toHaveLength(2);
    expect(screen.getByRole("heading", { name: "Brands" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Previous brands" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Next brands" })).toBeTruthy();
    expect(screen.getAllByRole("link", { name: /Olive Studio/ })[0].getAttribute("href")).toContain("brand=olive");
    expect(screen.getByRole("img", { name: "Olive Studio" }).getAttribute("src")).toContain("olive.webp");
    expect(screen.getAllByText("02").some((node) => node.closest(".live-store-brand-section"))).toBe(true);
    expect(document.querySelector(".live-store-brand-section + .live-store-category-section")).toBeTruthy();
    expect(screen.queryByText("Objects for everyday living")).toBeNull();
    expect(document.querySelector(".live-store-category-carousel").style.getPropertyValue("--store-carousel-columns")).toBe("2");
    expect(screen.getByRole("button", { name: "Previous categories" }).classList.contains("is-previous")).toBe(true);
    expect(screen.getByRole("button", { name: "Next categories" }).classList.contains("is-next")).toBe(true);
    expect(screen.getByRole("button", { name: "Previous categories" }).disabled).toBe(false);
    expect(screen.getByRole("button", { name: "Next categories" }).disabled).toBe(false);
    const categoryTrack = document.querySelectorAll(".live-store-category-carousel")[1];
    expect([...document.querySelectorAll(".live-store-category-carousel img")].every((image) => image.getAttribute("loading") === "lazy")).toBe(true);
    expect(screen.getByAltText("Olive tray").getAttribute("loading")).toBe("lazy");
    categoryTrack.scrollBy = vi.fn();
    fireEvent.click(screen.getByRole("button", { name: "Next categories" }));
    expect(categoryTrack.scrollBy).toHaveBeenCalledWith(expect.objectContaining({ behavior: "smooth" }));
    expect(document.querySelectorAll(".live-store-category-section")[1].querySelector(".live-store-category-media img")?.getAttribute("src")).toContain("home.webp");
    expect(screen.getAllByText("Olive tray").length).toBeGreaterThan(0);
    expect(screen.getAllByText("36").length).toBeGreaterThan(0);
    expect(screen.queryByText("Black")).toBeNull();
    expect(screen.queryByText("Sand")).toBeNull();
    expect(document.querySelector(".live-store-product-view")).toBeNull();
    expect(screen.getAllByRole("link", { name: "Add to cart" }).length).toBeGreaterThan(0);
    expect(screen.queryByText("NIKE / HOME")).toBeNull();
    expect(screen.getAllByAltText("Olive tray")).toHaveLength(1);
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
      <MemoryRouter initialEntries={["/shop"]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
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
      <MemoryRouter initialEntries={["/shop/categories"]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { level: 1, name: "Categories" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Gifts" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Home" }).getAttribute("href")).toBe("/shop");
    expect(screen.getAllByRole("link", { name: "Products" })[0].getAttribute("href")).toBe("/shop/catalog");

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
    ["home", "/shop", "Loading home page", "is-landing"],
    ["products", "/shop/catalog", "Loading products page", "is-catalog"],
    ["categories", "/shop/categories", "Loading categories page", "is-categories"],
    ["contact", "/shop/contact", "Loading contact page", "is-contact"],
    ["product details", "/shop/product/chair", "Loading product details page", "is-product"],
  ])("shows a page-shaped skeleton while loading %s", (_name, route, label, className) => {
    const pending = new Promise(() => {});
    fetchPublicEcommerceCatalog.mockReturnValue(pending);
    fetchPublicEcommerceProduct.mockReturnValue(pending);

    render(
      <MemoryRouter initialEntries={[route]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
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
      <MemoryRouter initialEntries={["/shop/catalog"]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
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
        subtotal: "25", discount_total: "0", delivery_fee: "5", total: "30", currency: "ILS",
        payment_status: "unpaid", status: "pending",
      },
      items: [{ id: "item-1", product_name: "Snapshot Product", sku: "SKU-1", quantity: 2, line_total: "25" }],
      status_history: [{ new_status: "pending", created_at: "2026-09-12T10:00:00Z" }],
    });

    render(
      <MemoryRouter initialEntries={[`/shop/confirmation/${token}`]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { level: 1, name: "MD-1001" })).toBeTruthy();
    expect(screen.getByText("Snapshot Product")).toBeTruthy();
    expect(screen.getByText(/Main Street/)).toBeTruthy();
    expect(screen.getByText("Delivery fee").parentElement.textContent).toContain("₪5.00");
    expect(screen.getByText("Total").parentElement.textContent).toContain("₪30.00");
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
      <MemoryRouter initialEntries={["/shop/catalog"]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
      </MemoryRouter>
    );

    expect((await screen.findAllByText("Chair")).length).toBeGreaterThan(0);
    expect(document.querySelector(".live-store").getAttribute("dir")).toBe("ltr");
    const languageButton = document.querySelector(".live-store-language");
    expect(languageButton.querySelector("svg")).toBeTruthy();
    expect(languageButton.textContent).toBe("");
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
      <MemoryRouter initialEntries={["/shop/checkout"]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { level: 1, name: "إتمام الطلب" })).toBeTruthy();
    const area = screen.getByLabelText("منطقة التوصيل");
    await screen.findByRole("option", { name: /^رام الله/ });
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
      <MemoryRouter initialEntries={["/shop/product/chair"]}>
        <Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes>
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
          announcement_link: "/shop/catalog",
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

    sessionStorage.setItem("madar-sale-bar:demo:20", "dismissed");

    render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);

    const announcement = await screen.findByText("Free local delivery this week");
    expect(announcement.closest(".live-store-announcement")).toBeTruthy();
    expect(screen.getAllByText("Featured Soap").length).toBeGreaterThan(0);
    expect(screen.queryByText("Latest")).toBeNull();
    expect(screen.getAllByText("$12.00").length).toBeGreaterThan(0);
    expect(document.querySelector(".live-store-product-sale-badge")?.textContent).toBe("Sale");
    expect(await screen.findByRole("dialog", { name: "Sale: up to 20% off" })).toBeTruthy();
    expect(screen.getByText("Sale now — up to 20% off selected items")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Dismiss sale popup" }));
    fireEvent.click(screen.getByRole("button", { name: "Dismiss sale announcement" }));
    expect(screen.queryByRole("dialog", { name: "Sale: up to 20% off" })).toBeNull();
    expect(screen.queryByText("Sale now — up to 20% off selected items")).toBeNull();
    const announcementLink = screen.getByRole("link", { name: "Free local delivery this week" });
    announcementLink.addEventListener("click", (event) => event.preventDefault(), { once: true });
    fireEvent.click(announcementLink);
    await waitFor(() => expect(received.map((item) => item.event)).toEqual(expect.arrayContaining(["promotion_view", "promotion_click"])));
    window.removeEventListener("madar:commerce", listener);
  });
});

it("uses safe visible feedback when a public product request fails", async () => {
  fetchPublicEcommerceProduct.mockRejectedValue(new Error("SUPABASE_SERVICE_KEY=private-key; SQL internal_product failed"));
  render(<MemoryRouter initialEntries={["/shop/product/chair"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);
  expect((await screen.findByRole("alert")).textContent).toContain("Could not load the live store");
  expect(document.body.textContent).not.toContain("SUPABASE_SERVICE_KEY");
  expect(document.body.textContent).not.toContain("internal_product");
});

it("shows a safe cart error instead of success when browser storage rejects an add", async () => {
  fetchPublicEcommerceProduct.mockResolvedValue({ site: { brand: "Store" }, product: { id: "product-1", slug: "chair", name: "Chair", price: "20", currency: "ILS", in_stock: true, images: [] }, category: null, tags: [], attributes: [], options: [], variants: [] });
  render(<MemoryRouter initialEntries={["/shop/product/chair"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);
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

it("keeps language selection in the hamburger and account access in the header", async () => {
  fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
  fetchPublicEcommerceProfile.mockResolvedValue({ site: catalog.site });
  render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);
  const accountTrigger = await screen.findByRole("button", { name: "Sign in or register" });
  expect(accountTrigger.querySelector("svg")).toBeTruthy();
  const toggle = document.querySelector(".live-store-mobile-menu");
  fireEvent.click(toggle);
  expect(document.querySelector(".live-store-menu-account")).toBeNull();
  fireEvent.click(document.querySelector(".live-store-menu-language button"));
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
});
it("closes the mobile navigation after a page selection and Escape", async () => {
  fetchPublicEcommerceCatalog.mockResolvedValue(catalog);
  fetchPublicEcommerceProfile.mockResolvedValue({ site: catalog.site });
  render(<MemoryRouter initialEntries={["/shop"]}><Routes><Route path="/shop/*" element={<EcommerceStorefront subdomain="demo" />} /></Routes></MemoryRouter>);
  await screen.findByRole("heading", { level: 1, name: "Test Store" });
  const toggle = document.querySelector(".live-store-mobile-menu");
  fireEvent.click(toggle);
  expect(toggle.getAttribute("aria-expanded")).toBe("true");
  expect(toggle.getAttribute("aria-controls")).toBe("live-store-mobile-navigation");
  fireEvent.click(document.querySelector('#live-store-mobile-navigation a[href="/shop/categories"]'));
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(toggle);
  fireEvent.keyDown(document, { key: "Escape" });
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
});
