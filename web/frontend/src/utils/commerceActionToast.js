// Only pass messages authored in the UI, never an API response or exception.
export function notifyCommerceAction(notification) {
  window.dispatchEvent(new CustomEvent("madar-commerce-action-toast", { detail: notification }));
}
