import { describe, expect, it } from "vitest";
import { commerceInventoryState, commerceProductStock } from "./commerceStock";

describe("commerce stock presentation", () => {
  it("handles simple inventory boundaries, disabled tracking, and backorders", () => {
    expect(commerceInventoryState({ track_inventory: true, inventory_quantity: 6, low_stock_threshold: 5 })).toBe("healthy");
    expect(commerceInventoryState({ track_inventory: true, inventory_quantity: 5, low_stock_threshold: 5 })).toBe("low_stock");
    expect(commerceInventoryState({ track_inventory: true, inventory_quantity: 0, low_stock_threshold: 5 })).toBe("out_of_stock");
    expect(commerceInventoryState({ track_inventory: false, inventory_quantity: 0 })).toBe("untracked");
    expect(commerceInventoryState({ track_inventory: true, inventory_quantity: 0, allow_backorder: true })).toBe("backorder");
  });

  it("uses active variant units instead of product inventory", () => {
    const result = commerceProductStock({
      track_inventory: true, inventory_quantity: 999, options: [{ id: "color" }],
      variants: [
        { active: true, track_inventory: true, inventory_quantity: 1, low_stock_threshold: 3 },
        { active: true, track_inventory: true, inventory_quantity: 0, low_stock_threshold: 3 },
        { active: true, track_inventory: true, inventory_quantity: 20, low_stock_threshold: 3 },
        { active: false, track_inventory: true, inventory_quantity: 0, low_stock_threshold: 3 },
      ],
    });
    expect(result).toEqual({ lowStock: 1, outOfStock: 1, state: "low_stock" });
  });
});
