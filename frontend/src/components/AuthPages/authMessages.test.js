import { describe, expect, it } from "vitest";

import { normalizeAuthMessage } from "./authMessages";

describe("normalizeAuthMessage", () => {
  it("keeps known user-safe auth messages", () => {
    expect(normalizeAuthMessage("Invalid email or password", "Try again.")).toBe(
      "Invalid email or password"
    );
  });

  it("replaces raw gateway and infrastructure errors with the fallback", () => {
    expect(normalizeAuthMessage("Bad Gateway", "Could not connect to the server.")).toBe(
      "Could not connect to the server."
    );
    expect(normalizeAuthMessage("upstream timeout", "Could not connect to the server.")).toBe(
      "Could not connect to the server."
    );
  });

  it("maps stable session codes to friendly messages", () => {
    expect(normalizeAuthMessage("auth.session.invalid", "Try again.")).toBe(
      "Your session is invalid or expired. Please log in again."
    );
  });
});
