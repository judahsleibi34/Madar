const IDEMPOTENCY_KEY_PREFIX = "madar-reservation";

export const createReservationIdempotencyKey = () => {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${IDEMPOTENCY_KEY_PREFIX}-${crypto.randomUUID()}`;
  }

  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    const value = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
    return `${IDEMPOTENCY_KEY_PREFIX}-${value}`;
  }

  return `${IDEMPOTENCY_KEY_PREFIX}-${Date.now().toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 12)}`;
};

export const getReservationErrorMessage = (error) => {
  if (error?.code === "reservation_slot_unavailable") {
    return "That time is no longer available. Choose another time and try again.";
  }

  if (error?.code === "idempotency_conflict") {
    return "This retry no longer matches your original request. Review the details and submit again.";
  }

  if (error?.status === 429) {
    return "Too many reservation attempts. Please wait and try again.";
  }

  if (error?.code === "submission_rejected") {
    return "This reservation request could not be accepted. Review it and try again.";
  }

  return "Could not send this reservation request. Your details are still here—please try again.";
};
