// Academies that opt in to live-only enrollment show "Enrollment opens soon"
// until a live provider is configured; the backend refuses checkout meanwhile.
export const enrollmentClosed = data => data?.enrollment_gate === true && data.enrollment_open !== true;
// Local simulation keeps the in-page Checkout; a hosted provider takes over the page.
export const paymentsAvailable = data => !enrollmentClosed(data) && Boolean(data?.local_adapter || data?.payments_available);
export const paymentNotice = data => data?.local_adapter ? "elearning.commerce.localOnly" : data?.payments_test_mode ? "elearning.commerce.testMode" : "elearning.commerce.securePayment";
export const testPayments = data => Boolean(data?.local_adapter || data?.payments_test_mode);
// Document states: Processing, Confirmed, Failed, Cancelled, Refunded.
export const checkoutStatus = state => ({ pending: "processing", paid: "confirmed", failed: "failed", cancelled: "cancelled", refunded: "refunded", reversed: "refunded" })[state] || "processing";
export function openCheckout(result, setCheckout) {
  const url = result.provider_session?.url;
  if (url && new URL(url).protocol === "https:") { window.location.assign(url); return; }
  setCheckout(result.checkout);
}
