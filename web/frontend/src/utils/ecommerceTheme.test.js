import { describe, expect, it } from "vitest";

import { MADAR_STORE_THEME, normalizeStoreTheme, readableForeground } from "./ecommerceTheme";

describe("normalizeStoreTheme", () => {
  it("upgrades the retired blue default to Madar colors", () => {
    expect(normalizeStoreTheme({
      accent: "#2463eb",
      background: "#ffffff",
      surface: "#f7f8fa",
      text: "#151821",
      muted: "#697181",
    })).toEqual({
      ...MADAR_STORE_THEME,
      seasonal_campaign: { enabled: false, type: "black_friday" },
    });
  });

  it("preserves a tenant's custom colors", () => {
    expect(normalizeStoreTheme({ accent: "#287a55" }).accent).toBe("#287a55");
  });

  it("normalizes the supported seasonal campaign", () => {
    expect(normalizeStoreTheme({
      seasonal_campaign: { enabled: true, type: "other" },
    }).seasonal_campaign).toEqual({ enabled: true, type: "black_friday" });
  });
});

describe("readableForeground", () => {
  it("selects a readable foreground for light and dark merchant accents", () => {
    expect(readableForeground("#f5c542")).toBe("#080808");
    expect(readableForeground("#162033")).toBe("#ffffff");
    expect(readableForeground("invalid")).toBe("#ffffff");
  });
});
