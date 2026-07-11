import { describe, expect, it } from "vitest";

import { formatAuthValidationToastMessage, normalizeAuthMessage } from "./authMessages";

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

describe("formatAuthValidationToastMessage", () => {
  it("keeps required-field summaries compact", () => {
    expect(
      formatAuthValidationToastMessage(
        {
          firstName: "This field is required.",
          email: "This field is required.",
        },
        {
          firstName: "First name",
          email: "Email",
        }
      )
    ).toBe("First name and Email are required.");
  });

  it("includes explicit field problems for non-required errors", () => {
    expect(
      formatAuthValidationToastMessage(
        {
          email: "Please enter a valid email address.",
          password: "Password must include a number.",
        },
        {
          email: "Email",
          password: "Password",
        }
      )
    ).toBe("Email: Please enter a valid email address. Password: Password must include a number.");
  });
});
