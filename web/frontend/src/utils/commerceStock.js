export function commerceInventoryState(item) {
  if (!item?.track_inventory) return "untracked";
  const quantity = Number(item.inventory_quantity || 0);
  if (quantity <= 0) return item.allow_backorder ? "backorder" : "out_of_stock";
  if (item.low_stock_threshold != null && quantity <= Number(item.low_stock_threshold)) return "low_stock";
  return "healthy";
}

export function commerceProductStock(product) {
  const activeVariants = (product?.variants || []).filter((variant) => variant.active !== false);
  if ((product?.options || []).length) {
    const states = activeVariants.map(commerceInventoryState);
    return {
      lowStock: states.filter((state) => state === "low_stock").length,
      outOfStock: states.filter((state) => state === "out_of_stock").length,
      state: !states.length || states.every((state) => state === "out_of_stock") ? "out_of_stock" : states.some((state) => state === "low_stock" || state === "out_of_stock") ? "low_stock" : "healthy",
    };
  }
  const state = commerceInventoryState(product);
  return { lowStock: state === "low_stock" ? 1 : 0, outOfStock: state === "out_of_stock" ? 1 : 0, state };
}
