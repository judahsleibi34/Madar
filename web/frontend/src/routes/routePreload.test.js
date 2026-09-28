import { expect, it } from "vitest";
import { getRoutePreloader, preloadRoute, shouldPreloadCurrentRoute } from "./routePreload";

it("maps page destinations, including editors and storefronts", () => {
  for (const path of ["/settings", "/notifications", "/ecommerce/products/new", "/ecommerce/products/123/edit", "/ecommerce/orders", "/ecommerce/social-links", "/calendar", "/shop", "/shop/product/shirt", "/ecommerce-preview/demo", "/login", "/contact"]) expect(getRoutePreloader(path)).toBeTypeOf("function");
  expect(getRoutePreloader("/unknown")).toBeUndefined();
  expect(getRoutePreloader("/ecommerce/products/new")).not.toBe(getRoutePreloader("/ecommerce/products"));
});
it("ignores external links and respects reduced-data connections", () => {
  expect(preloadRoute("https://external.example/settings", {origin:"http://localhost:5173"})).toBeUndefined();
  expect(preloadRoute("/settings", {origin:"http://localhost:5173", connection:{saveData:true}})).toBeUndefined();
  expect(preloadRoute("/settings", {origin:"http://localhost:5173", connection:{effectiveType:"2g"}})).toBeUndefined();
});
it("eagerly preloads only direct product editor routes", () => {
  expect(shouldPreloadCurrentRoute("/ecommerce/products/new")).toBe(true);
  expect(shouldPreloadCurrentRoute("/ecommerce/products/123/edit")).toBe(true);
  expect(shouldPreloadCurrentRoute("/ecommerce/products")).toBe(false);
  expect(shouldPreloadCurrentRoute("/settings")).toBe(false);
});
