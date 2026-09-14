const COMMERCE_EVENTS = new Set([
  "view_item_list", "view_item", "add_to_cart", "remove_from_cart", "view_cart", "begin_checkout", "purchase", "promotion_view", "promotion_click",
]);

const FORBIDDEN_KEYS = new Set([
  "email", "customer_email", "phone", "customer_phone", "street", "building", "floor", "floor_apartment",
  "address", "address_line_1", "address_description", "delivery_notes", "notes", "confirmation_token",
  "payment_collected_by", "payment_actor", "customer_name",
]);

const sanitize = (value) => {
  if (Array.isArray(value)) return value.map(sanitize);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.entries(value).filter(([key]) => !FORBIDDEN_KEYS.has(key)).map(([key, item]) => [key, sanitize(item)]));
};

export function trackCommerceEvent(eventName, payload = {}) {
  if (!COMMERCE_EVENTS.has(eventName)) return false;
  const detail = Object.freeze({ event: eventName, payload: sanitize(payload) });
  const dispatch = () => {
    try {
      globalThis.window?.dispatchEvent?.(new CustomEvent("madar:commerce", { detail }));
      const provider = globalThis.window?.madarAnalytics;
      if (typeof provider?.track === "function") Promise.resolve(provider.track(eventName, detail.payload)).catch(() => {});
    } catch { /* Analytics is observational and must never affect commerce. */ }
  };
  if (typeof globalThis.queueMicrotask === "function") globalThis.queueMicrotask(dispatch);
  else Promise.resolve().then(dispatch).catch(() => {});
  return true;
}

export function trackPurchaseOnce(order, items = [], locale = "en") {
  const orderId = String(order?.id || order?.order_number || "");
  if (!orderId) return false;
  const key = `madar:commerce:purchase:${orderId}`;
  try {
    if (globalThis.sessionStorage?.getItem(key)) return false;
    globalThis.sessionStorage?.setItem(key, "1");
  } catch { /* Event still remains non-blocking when storage is unavailable. */ }
  return trackCommerceEvent("purchase", {
    order_id: orderId,
    items: items.map((item) => ({ product_id: item.product_id, variant_id: item.variant_id || null, quantity: Number(item.quantity || 0) })),
    subtotal: Number(order.subtotal || 0), discount_total: Number(order.discount_total || 0), total: Number(order.total || 0),
    currency: order.currency, locale,
  });
}

export const COMMERCE_EVENT_NAMES = Object.freeze([...COMMERCE_EVENTS]);
