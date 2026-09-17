import { describe, expect, it } from "vitest";

import { MADAR_STORE_THEME, normalizeStoreTheme } from "./ecommerceTheme";

describe("normalizeStoreTheme", () => {
  it("upgrades the retired blue default to Madar colors", () => {
    expect(normalizeStoreTheme({
      accent: "#2463eb",
      background: "#ffffff",
      surface: "#f7f8fa",
      text: "#151821",
      muted: "#697181",
    })).toEqual(MADAR_STORE_THEME);
  });

  it("preserves a tenant's custom colors", () => {
    expect(normalizeStoreTheme({ accent: "#287a55" }).accent).toBe("#287a55");
  });
});
