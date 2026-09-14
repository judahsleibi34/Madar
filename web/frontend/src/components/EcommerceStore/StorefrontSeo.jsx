/* eslint-disable react-refresh/only-export-components -- colocated pure metadata builders keep the head contract directly testable. */
import { useEffect } from "react";

const SCHEMA_ORIGIN = "https://schema.org";

const localizedSetting = (growth, prefix, locale) => {
  const primary = String(growth?.[`${prefix}_${locale === "ar" ? "ar" : "en"}`] || "").trim();
  const fallback = String(growth?.[`${prefix}_${locale === "ar" ? "en" : "ar"}`] || "").trim();
  return primary || fallback;
};

export const safePublicUrl = (value, origin) => {
  const candidate = String(value || "").trim();
  if (!candidate || ["\r", "\n", "\\", String.fromCharCode(0)].some((character) => candidate.includes(character))) return "";
  try {
    const base = new URL(origin);
    const parsed = new URL(candidate, origin);
    if (!/^https?:$/.test(parsed.protocol) || parsed.username || parsed.password) return "";
    if (parsed.protocol !== "https:" && parsed.origin !== base.origin) return "";
    if (/\/(?:private|private-uploads)(?:\/|$)/i.test(parsed.pathname)) return "";
    return parsed.href;
  } catch {
    return "";
  }
};

const cleanCanonical = (origin, path, query = "") => {
  const normalizedPath = `/${String(path || "").replace(/^\/+|\/+$/g, "")}`.replace(/\/$/, "");
  return `${origin}${normalizedPath || "/"}${query}`;
};

const productStructuredData = ({ product, variants, canonical, image }) => {
  const data = {
    "@context": SCHEMA_ORIGIN,
    "@type": "Product",
    name: product.name,
    url: canonical,
  };
  if (product.description) data.description = product.description;
  if (product.sku) data.sku = product.sku;
  if (image) data.image = [image];

  const activeVariants = (variants || []).filter((variant) => variant.active !== false);
  const prices = activeVariants.map((variant) => Number(variant.price)).filter(Number.isFinite);
  if (activeVariants.length && prices.length) {
    const availabilityValues = activeVariants.map((variant) => variant.seo_availability || (variant.in_stock ? "InStock" : "OutOfStock"));
    const availability = availabilityValues.includes("InStock")
      ? "InStock"
      : availabilityValues.includes("BackOrder") ? "BackOrder" : "OutOfStock";
    data.offers = {
      "@type": "AggregateOffer",
      priceCurrency: product.currency,
      lowPrice: String(Math.min(...prices)),
      highPrice: String(Math.max(...prices)),
      offerCount: prices.length,
      availability: `${SCHEMA_ORIGIN}/${availability}`,
    };
  } else if (Number.isFinite(Number(product.price))) {
    data.offers = {
      "@type": "Offer",
      price: String(product.price),
      priceCurrency: product.currency,
      availability: `${SCHEMA_ORIGIN}/${product.seo_availability || (product.in_stock ? "InStock" : "OutOfStock")}`,
      url: canonical,
    };
  }
  return data;
};

export function buildStorefrontSeo({
  origin,
  storePath,
  locale,
  site,
  productDetail,
  category,
  view,
}) {
  const brand = String(site?.brand || site?.footer_store_name || "").trim();
  const growth = site?.growth || {};
  const privateView = ["checkout", "confirmation", "preview", "missing"].includes(view);
  const product = productDetail?.product;
  let title = localizedSetting(growth, "seo_title", locale) || brand;
  let description = localizedSetting(growth, "seo_description", locale) || String(site?.description || "").trim();
  let canonical = "";
  let type = "website";
  let structuredData = null;

  if (!privateView) {
    if (product) {
      title = `${product.seo_title || product.name}${brand ? ` | ${brand}` : ""}`;
      description = String(product.seo_description || product.description || description).trim();
      canonical = cleanCanonical(origin, `${storePath}/product/${encodeURIComponent(product.slug)}`);
      type = "product";
    } else if (category) {
      title = `${category.name}${brand ? ` | ${brand}` : ""}`;
      description = String(category.description || description).trim();
      canonical = cleanCanonical(origin, `${storePath}/catalog`, `?category=${encodeURIComponent(category.slug)}`);
    } else if (view === "catalog") {
      title = `${locale === "ar" ? "المنتجات" : "Products"}${brand ? ` | ${brand}` : ""}`;
      canonical = cleanCanonical(origin, `${storePath}/catalog`);
    } else if (view === "categories") {
      title = `${locale === "ar" ? "التصنيفات" : "Categories"}${brand ? ` | ${brand}` : ""}`;
      canonical = cleanCanonical(origin, `${storePath}/categories`);
    } else if (view === "contact") {
      title = `${locale === "ar" ? "تواصل معنا" : "Contact"}${brand ? ` | ${brand}` : ""}`;
      canonical = cleanCanonical(origin, `${storePath}/contact`);
    } else {
      canonical = cleanCanonical(origin, storePath);
    }
  }

  const rawImage = product?.images?.[0] || site?.logo_url || site?.loading_image_url;
  const image = safePublicUrl(rawImage, origin);
  if (product && canonical) {
    structuredData = productStructuredData({ product, variants: productDetail?.variants, canonical, image });
  } else if (canonical && brand) {
    structuredData = { "@context": SCHEMA_ORIGIN, "@type": "Organization", name: brand, url: canonical };
    if (image) structuredData.logo = image;
  }

  return {
    title: title || (locale === "ar" ? "متجر" : "Store"),
    description: description.slice(0, 320),
    canonical,
    image,
    type,
    robots: privateView ? "noindex,nofollow,noarchive" : "index,follow",
    structuredData,
  };
}

const appendHeadElement = (tagName, attributes, text = "") => {
  const element = document.createElement(tagName);
  element.setAttribute("data-madar-storefront-seo", "true");
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  if (text) element.textContent = text;
  document.head.appendChild(element);
};

export default function StorefrontSeo(props) {
  const signature = JSON.stringify(buildStorefrontSeo(props));

  useEffect(() => {
    const metadata = JSON.parse(signature);
    const previousTitle = document.title;
    document.querySelectorAll("[data-madar-storefront-seo]").forEach((element) => element.remove());
    document.title = metadata.title;
    appendHeadElement("meta", { name: "robots", content: metadata.robots });
    if (metadata.description) appendHeadElement("meta", { name: "description", content: metadata.description });
    if (metadata.canonical) {
      appendHeadElement("link", { rel: "canonical", href: metadata.canonical });
      appendHeadElement("meta", { property: "og:title", content: metadata.title });
      if (metadata.description) appendHeadElement("meta", { property: "og:description", content: metadata.description });
      appendHeadElement("meta", { property: "og:url", content: metadata.canonical });
      appendHeadElement("meta", { property: "og:type", content: metadata.type });
      if (metadata.image) appendHeadElement("meta", { property: "og:image", content: metadata.image });
    }
    if (metadata.structuredData) {
      appendHeadElement("script", { type: "application/ld+json" }, JSON.stringify(metadata.structuredData).replace(/</g, "\\u003c"));
    }
    return () => {
      document.querySelectorAll("[data-madar-storefront-seo]").forEach((element) => element.remove());
      document.title = previousTitle;
    };
  }, [signature]);

  return null;
}
