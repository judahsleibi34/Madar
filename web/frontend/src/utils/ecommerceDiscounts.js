// Preview only: checkout recomputes all eligibility and monetary snapshots in SQL.
const validAt = (condition, startsAt, now) => condition.validity_mode === "lifetime"
  || (Number.isFinite(Date.parse(startsAt)) && Date.parse(startsAt) + Number(condition.validity_days) * 86400000 > now);

export const productDiscountBasisPoints = (productId, normalConditions = [], entitlements = [], now = Date.now()) => {
  let best = 0;
  for (const condition of normalConditions) {
    if (condition.product_ids?.includes(String(productId)) && validAt(condition, condition.starts_at, now)) {
      best = Math.max(best, Number(condition.discount_basis_points) || 0);
    }
  }
  for (const entitlement of entitlements) {
    if (entitlement.status !== "active" || (entitlement.expires_at && Date.parse(entitlement.expires_at) <= now)) continue;
    if (entitlement.reward_conditions?.length) {
      for (const condition of entitlement.reward_conditions) {
        if (condition.product_ids?.includes(String(productId)) && validAt(condition, entitlement.granted_at, now)) {
          best = Math.max(best, Number(condition.discount_basis_points) || 0);
        }
      }
    } else if (String(entitlement.reward_product_id) === String(productId)) {
      best = Math.max(best, Number(entitlement.reward_discount_basis_points) || 0);
    }
  }
  return Math.min(10000, Math.max(0, best));
};

export const estimateCartDiscount = (items, normalConditions, entitlements, now = Date.now()) =>
  items.reduce((total, item) => {
    const basisPoints = productDiscountBasisPoints(item.id, normalConditions, entitlements, now);
    const listUnitCents = Math.round((Number(item.price) || 0) * 100);
    const unitDiscountCents = Math.round(listUnitCents * basisPoints / 10000);
    return total + unitDiscountCents * (Number(item.quantity) || 0) / 100;
  }, 0);
