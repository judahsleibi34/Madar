// Local simulation keeps the in-page Checkout; a hosted provider takes over the page.
export const paymentsAvailable = data => Boolean(data?.local_adapter || data?.payments_available);
export const paymentNotice = data => data?.local_adapter ? "elearning.commerce.localOnly" : data?.payments_test_mode ? "elearning.commerce.testMode" : "elearning.commerce.securePayment";
export function openCheckout(result, setCheckout) {
  const url = result.provider_session?.url;
  if (url && new URL(url).protocol === "https:") { window.location.assign(url); return; }
  setCheckout(result.checkout);
}
