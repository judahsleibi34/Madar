// Single source of truth for the storefront's primary read. The storefront
// component and the hosted-tenant entry prefetch both derive the request from
// these helpers, so an early prefetch always targets the exact cache entry the
// component will read.

export const parseStorefrontRoute = (routeTail = "") => {
  const tail = String(routeTail || "");
  return {
    productSlug: tail.match(/^(?:catalog\/)?product\/([^/]+)\/?$/)?.[1] || "",
    contactRoute: /^contact\/?$/.test(tail),
    checkoutRoute: /^checkout\/?$/.test(tail),
    confirmationToken: tail.match(/^confirmation\/([0-9a-f]{64})\/?$/)?.[1] || "",
  };
};

export const readStorefrontFilters = (urlFilters, locale) => ({
  search: urlFilters.get("search") || "",
  category: urlFilters.get("category") || "",
  brand: urlFilters.get("brand") || "",
  tag: urlFilters.get("tag") || "",
  minPrice: urlFilters.get("min_price") || "",
  maxPrice: urlFilters.get("max_price") || "",
  sort: urlFilters.get("sort") || "latest",
  page: urlFilters.get("page") || "1",
  locale,
});

export const buildStorefrontPrimaryRequest = ({
  productSlug,
  contactRoute,
  checkoutRoute,
  confirmationToken,
  filters,
  locale,
}) => {
  if (confirmationToken) return { type: "confirmation", token: confirmationToken };
  if (productSlug) return { type: "product", slug: productSlug, locale };
  if (contactRoute || checkoutRoute) return { type: "profile" };
  return {
    type: "catalog",
    filters: {
      search: filters.search,
      category: filters.category,
      brand: filters.brand,
      tag: filters.tag,
      min_price: filters.minPrice,
      max_price: filters.maxPrice,
      sort: filters.sort,
      page: filters.page,
      locale,
      limit: "12",
    },
  };
};

export const getStorefrontPrimaryRequest = ({ routeTail = "", search = "", locale = "en" } = {}) =>
  buildStorefrontPrimaryRequest({
    ...parseStorefrontRoute(routeTail),
    filters: readStorefrontFilters(new URLSearchParams(search), locale),
    locale,
  });
