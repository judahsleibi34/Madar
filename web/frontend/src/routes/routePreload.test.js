import { expect, it } from "vitest";
import { getRoutePreloader, preloadRoute } from "./routePreload";

it("maps page destinations, including editors and storefronts", () => {
  for (const path of ["/settings", "/notifications", "/ecommerce/products/new", "/ecommerce/products/123/edit", "/ecommerce/orders", "/calendar", "/shop", "/site/demo/shop/product/shirt", "/login", "/contact"]) expect(getRoutePreloader(path)).toBeTypeOf("function");
  expect(getRoutePreloader("/unknown")).toBeUndefined();
  expect(getRoutePreloader("/ecommerce/products/new")).not.toBe(getRoutePreloader("/ecommerce/products"));
});
it("ignores external links and respects reduced-data connections", () => {
  expect(preloadRoute("https://external.example/settings", {origin:"http://localhost:5173"})).toBeUndefined();
  expect(preloadRoute("/settings", {origin:"http://localhost:5173", connection:{saveData:true}})).toBeUndefined();
  expect(preloadRoute("/settings", {origin:"http://localhost:5173", connection:{effectiveType:"2g"}})).toBeUndefined();
});
