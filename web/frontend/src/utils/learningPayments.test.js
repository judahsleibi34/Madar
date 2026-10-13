import { afterEach, describe, expect, it, vi } from "vitest";
import { openCheckout, paymentNotice, paymentsAvailable } from "./learningPayments";

describe("learning payments", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("hands hosted sessions to the provider page and keeps local checkouts in place", () => {
    const assign = vi.fn(), setCheckout = vi.fn();
    vi.stubGlobal("location", { assign });
    openCheckout({ checkout: { id: "c1" }, provider_session: { url: "https://checkout.stripe.com/c/pay/cs_test" } }, setCheckout);
    expect(assign).toHaveBeenCalledWith("https://checkout.stripe.com/c/pay/cs_test");
    expect(setCheckout).not.toHaveBeenCalled();
    openCheckout({ checkout: { id: "c2" } }, setCheckout);
    expect(setCheckout).toHaveBeenCalledWith({ id: "c2" });
  });

  it("never navigates to a non-https provider URL", () => {
    const assign = vi.fn(), setCheckout = vi.fn();
    vi.stubGlobal("location", { assign });
    openCheckout({ checkout: { id: "c3" }, provider_session: { url: "javascript:alert(1)" } }, setCheckout);
    expect(assign).not.toHaveBeenCalled();
    expect(setCheckout).toHaveBeenCalledWith({ id: "c3" });
  });

  it("describes availability and test mode", () => {
    expect(paymentsAvailable({ payments_available: true })).toBe(true);
    expect(paymentsAvailable({})).toBe(false);
    expect(paymentNotice({ local_adapter: true })).toBe("elearning.commerce.localOnly");
    expect(paymentNotice({ payments_test_mode: true })).toBe("elearning.commerce.testMode");
    expect(paymentNotice({ payments_available: true })).toBe("elearning.commerce.securePayment");
  });
});
