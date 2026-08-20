import { afterEach, describe, expect, it } from "vitest";

import {
  clearPendingVerificationEmail,
  getVerificationErrorState,
  isEmailVerificationRequiredError,
  maskEmail,
  readPendingVerificationEmail,
  readVerificationCallback,
  rememberPendingVerificationEmail,
} from "./emailVerification";

afterEach(() => {
  clearPendingVerificationEmail();
});

describe("email verification state helpers", () => {
  it("masks pending email without exposing the full address", () => {
    expect(maskEmail("Owner@Example.com")).toBe("o***@e***.com");
    expect(maskEmail("invalid")).toBe("your email address");
  });

  it("keeps the pending address only in session storage", () => {
    rememberPendingVerificationEmail(" Owner@Example.com ");

    expect(readPendingVerificationEmail()).toBe("owner@example.com");
    expect(window.localStorage.getItem("madar.pending-verification-email")).toBeNull();
  });

  it("parses provider fragments without treating a query flag as verification", () => {
    const callback = readVerificationCallback({
      hash: "#access_token=secret&type=signup",
      search: "?verified=true",
    });

    expect(callback.accessToken).toBe("secret");
    expect(callback.callbackType).toBe("signup");
    expect(callback.hasProviderError).toBe(false);
    expect(callback).not.toHaveProperty("verified");
  });

  it("classifies expired and invalid provider failures safely", () => {
    expect(getVerificationErrorState({ errorCode: "otp_expired" })).toBe("expired");
    expect(getVerificationErrorState({ error: "access_denied" })).toBe("invalid");
  });

  it("recognizes structured and legacy unverified-login responses", () => {
    expect(
      isEmailVerificationRequiredError({
        detail: {
          code: "email_verification_required",
          message: "Verify your email before logging in.",
        },
      })
    ).toBe(true);
    expect(
      isEmailVerificationRequiredError({
        detail: "Please verify your email before logging in",
      })
    ).toBe(true);
    expect(isEmailVerificationRequiredError({ detail: "Invalid email or password" })).toBe(false);
  });
});
