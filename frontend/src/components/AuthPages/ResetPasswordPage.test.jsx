import { describe, expect, it } from "vitest";

import { readRecoveryContext } from "./resetPasswordRecovery";

describe("password recovery URL handling", () => {
  it("binds the provider recovery token and hashed-request nonce context", () => {
    expect(
      readRecoveryContext({
        hash: "#access_token=provider-token&type=recovery",
        search: "?request_token=request-nonce",
      })
    ).toEqual({
      accessToken: "provider-token",
      requestToken: "request-nonce",
      providerError: false,
    });
  });

  it("accepts provider recovery parameters in the query without using a homepage fallback", () => {
    expect(
      readRecoveryContext({
        hash: "",
        search: "?access_token=provider-token&type=recovery&request_token=request-nonce",
      })
    ).toEqual({
      accessToken: "provider-token",
      requestToken: "request-nonce",
      providerError: false,
    });
  });

  it("does not accept non-recovery provider fragments", () => {
    expect(
      readRecoveryContext({
        hash: "#access_token=provider-token&type=signup",
        search: "",
      }).accessToken
    ).toBeNull();
  });
});
