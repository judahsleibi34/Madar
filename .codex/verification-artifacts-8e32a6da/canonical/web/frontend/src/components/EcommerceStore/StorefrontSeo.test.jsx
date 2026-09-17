import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import StorefrontSeo, { buildStorefrontSeo, safePublicUrl } from "./StorefrontSeo";

afterEach(() => cleanup());

const site = {
  brand: "Olive House",
  description: "Local olive goods",
  logo_url: "https://cdn.example.com/logo.webp",
  growth: {
    seo_title_en: "Olive store",
    seo_title_ar: "متجر الزيتون",
    seo_description_en: "Merchant supplied description",
    seo_description_ar: "وصف التاجر",
  },
};

describe("storefront SEO", () => {
  it("builds localized store and category metadata with canonical URLs", () => {
    const home = buildStorefrontSeo({ origin: "https://madarportal.com", storePath: "/site/olive/shop", locale: "ar", site, view: "home" });
    expect(home.title).toBe("متجر الزيتون");
    expect(home.description).toBe("وصف التاجر");
    expect(home.canonical).toBe("https://madarportal.com/site/olive/shop");

    const category = buildStorefrontSeo({ origin: "https://madarportal.com", storePath: "/site/olive/shop", locale: "en", site, category: { name: "Gifts", slug: "gifts", description: "Thoughtful gifts" }, view: "catalog" });
    expect(category.title).toBe("Gifts | Olive House");
    expect(category.canonical).toBe("https://madarportal.com/site/olive/shop/catalog?category=gifts");
  });

  it("emits truthful simple and aggregate product offers", () => {
    const base = { origin: "https://madarportal.com", storePath: "/site/olive/shop", locale: "en", site, view: "product" };
    const simple = buildStorefrontSeo({ ...base, productDetail: { product: { name: "Soap", slug: "soap", sku: "SOAP", price: "10.00", currency: "ILS", in_stock: false, seo_availability: "OutOfStock", images: ["https://cdn.example.com/soap.webp"] }, variants: [] } });
    expect(simple.type).toBe("product");
    expect(simple.structuredData.offers).toMatchObject({ "@type": "Offer", price: "10.00", priceCurrency: "ILS", availability: "https://schema.org/OutOfStock" });
    expect(simple.image).toBe("https://cdn.example.com/soap.webp");

    const variant = buildStorefrontSeo({ ...base, productDetail: { product: { name: "Shirt", slug: "shirt", currency: "USD", images: [] }, variants: [{ price: "20", active: true, seo_availability: "OutOfStock" }, { price: "25", active: true, seo_availability: "BackOrder" }, { price: "5", active: false, seo_availability: "InStock" }] } });
    expect(variant.structuredData.offers).toMatchObject({ "@type": "AggregateOffer", lowPrice: "20", highPrice: "25", offerCount: 2, availability: "https://schema.org/BackOrder" });
  });

  it("does not expose confirmation URLs or private media", () => {
    const metadata = buildStorefrontSeo({ origin: "https://madarportal.com", storePath: "/shop", locale: "en", site, view: "confirmation" });
    expect(metadata.robots).toContain("noindex");
    expect(metadata.canonical).toBe("");
    expect(safePublicUrl("http://cdn.example.com/customer.jpg", "https://madarportal.com")).toBe("");
    expect(metadata.structuredData).toBeNull();
    expect(JSON.stringify(metadata)).not.toContain("confirmation");
    expect(safePublicUrl("/private-uploads/customer.jpg", "https://madarportal.com")).toBe("");
    expect(safePublicUrl("javascript:alert(1)", "https://madarportal.com")).toBe("");
  });

  it("installs and cleans native document head tags", () => {
    const previous = document.title;
    const rendered = render(<StorefrontSeo origin="https://madarportal.com" storePath="/site/olive/shop" locale="en" site={site} view="home" />);
    expect(document.title).toBe("Olive store");
    expect(document.head.querySelector('link[rel="canonical"]')?.href).toBe("https://madarportal.com/site/olive/shop");
    expect(document.head.querySelector('meta[property="og:title"]')?.content).toBe("Olive store");
    expect(JSON.parse(document.head.querySelector('script[type="application/ld+json"]')?.textContent)["@type"]).toBe("Organization");
    rendered.unmount();
    expect(document.head.querySelector("[data-madar-storefront-seo]")).toBeNull();
    expect(document.title).toBe(previous);
  });
});
