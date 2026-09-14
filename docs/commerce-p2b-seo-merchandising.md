# Commerce P2-B: storefront SEO and merchandising

P2-B is a presentation and discovery layer over the existing commerce catalog. It does not change product pricing, variants, inventory, checkout, orders, or loyalty.

## Persistence and validation

No schema migration is required. The existing `website_settings.ecommerce_theme` JSON object now preserves a validated nested `growth` object containing two localized store SEO overrides, a localized content announcement, one optional safe link, and ordered references to active tenant products and categories. Merchant writes require the existing e-commerce role checks. Featured references are checked against active rows in the same tenant before saving, and public catalog cache entries are invalidated after a successful update.

The announcement accepts plain text only. Links must be relative paths or HTTPS URLs without credentials or control characters. It does not affect prices.

## Public SEO

The React storefront manages native document-head elements for public home, catalog, category-filter, category-directory, contact, and product views. It emits localized titles and descriptions, canonical links, Open Graph metadata, robots directives, and JSON-LD. Product JSON-LD uses a concrete `Offer` for simple products and an `AggregateOffer` for active variants; availability is derived from the existing simple or variant inventory/backorder state.

Checkout, confirmation-token, draft-preview, and unresolved product views receive `noindex,nofollow,noarchive` and do not emit canonical, Open Graph URL, or structured-data elements. The head manager never includes customer or order data.

Canonical URLs normalize the legacy `/store/:identifier` alias to `/site/:identifier/shop`. Branded storefronts use `/shop`. Category identity uses the existing stable `?category=<slug>` route. Search, sort, tag, and pagination parameters are not canonical identities. The current locale is application state rather than a stable locale URL, so fake `hreflang` alternates are intentionally not emitted.

Tenant-scoped backend endpoints expose an XML sitemap and a defensive robots response at `/public/sites/{identifier}/sitemap.xml` and `/public/sites/{identifier}/robots.txt`. The sitemap contains only the storefront, active categories, and active products returned by the existing public catalog source. It cannot contain cart, checkout, customer, dashboard, or confirmation-token URLs. The frontend also ships a root `robots.txt` that discourages indexing of private and transactional routes; robots directives are not authorization controls.

## Merchandising and analytics

The existing Store Design page provides explicit Save controls for SEO overrides, the announcement, and featured products/categories. The storefront preserves configured ordering and silently excludes inactive references. With no configured selections, the existing latest-products and top-level-category presentation remains the fallback.

The announcement records non-blocking `promotion_view` and `promotion_click` events through the existing analytics adapter. Payloads contain only store identifier, locale, and placement.

## SPA limitation

Metadata is installed after the React application loads. JavaScript-capable crawlers and social tooling that renders the SPA can observe it, but the initial static HTML shell is not tenant-specific. Reliable metadata for all crawlers and link unfurlers still requires edge rendering, prerendering, or SSR. P2-B does not introduce a framework migration or claim server-rendered SEO.
