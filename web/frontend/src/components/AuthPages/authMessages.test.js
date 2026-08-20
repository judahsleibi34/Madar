import { describe, expect, it } from "vitest";

import { normalizeAuthMessage } from "./authMessages";

describe("normalizeAuthMessage", () => {
  it("surfaces a rejected-origin response instead of reporting a connection failure", () => {
    expect(normalizeAuthMessage("Invalid request origin", "Could not connect to the server.")).toBe(
      "Invalid request origin"
    );
  });

  it("surfaces the platform-account login guidance", () => {
    const message = "Use the login page for the website where this account was created.";

    expect(normalizeAuthMessage(message, "Could not connect to the server.")).toBe(message);
  });
});
