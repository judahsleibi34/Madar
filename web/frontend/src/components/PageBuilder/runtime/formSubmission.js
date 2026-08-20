const IDEMPOTENCY_KEY_PREFIX = "madar-form";

export const createFormIdempotencyKey = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${IDEMPOTENCY_KEY_PREFIX}-${crypto.randomUUID()}`;
  }
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    const value = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
    return `${IDEMPOTENCY_KEY_PREFIX}-${value}`;
  }
  return `${IDEMPOTENCY_KEY_PREFIX}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
};
