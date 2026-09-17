import { expect, it } from "vitest";
import { estimateCartDiscount, productDiscountBasisPoints } from "./ecommerceDiscounts";

const now = Date.parse("2026-09-16T12:00:00Z");
const normal = [{ product_ids:["a","b"], discount_basis_points:2000, validity_mode:"lifetime" }];
const entitlements = [{ status:"active", granted_at:"2026-09-01T12:00:00Z", reward_conditions:[
  { product_ids:["a","b"], discount_basis_points:3000, validity_mode:"fixed_period", validity_days:30 },
  { product_ids:["b"], discount_basis_points:1000, validity_mode:"lifetime" },
] }];
it("selects the higher percentage per product without stacking", () => {
  expect(productDiscountBasisPoints("a", normal, entitlements, now)).toBe(3000);
  expect(productDiscountBasisPoints("a", normal, [], now)).toBe(2000);
  expect(productDiscountBasisPoints("other", normal, entitlements, now)).toBe(0);
  expect(productDiscountBasisPoints("a", [{ ...normal[0], discount_basis_points:4000 }], entitlements, now)).toBe(4000);
});
it("expires fixed conditions independently and excludes revoked rewards", () => {
  const later = Date.parse("2026-10-16T12:00:00Z");
  expect(productDiscountBasisPoints("b", [], entitlements, later)).toBe(1000);
  expect(productDiscountBasisPoints("a", normal, entitlements, later)).toBe(2000);
  expect(productDiscountBasisPoints("b", [], [{ ...entitlements[0], status:"revoked" }], now)).toBe(0);
});
it("rounds each unit before multiplying quantity and retains legacy reward previews", () => {
  expect(estimateCartDiscount([{ id:"a", price:.05, quantity:3 }], [{ ...normal[0], discount_basis_points:1000 }], [], now)).toBe(.03);
  expect(productDiscountBasisPoints("a", [], [{ status:"active", reward_product_id:"a", reward_discount_basis_points:1000 }], now)).toBe(1000);
});
