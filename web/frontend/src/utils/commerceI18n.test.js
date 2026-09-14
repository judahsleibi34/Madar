import { describe, expect, it } from "vitest";

import { formatCommerceDateTime, formatCommerceMoney, localizeCommerceValue } from "./commerceI18n";

describe("commerce localization formatters", () => {
  it("selects localized merchant data with safe fallback", () => {
    const value = { name_translations: { en: "Color", ar: "اللون" } };
    expect(localizeCommerceValue(value, "ar", "name")).toBe("اللون");
    expect(localizeCommerceValue({ name_translations: { en: "Color" } }, "ar", "name")).toBe("Color");
    expect(localizeCommerceValue({ name_translations: { ar: "اللون" } }, "en", "name")).toBe("اللون");
  });

  it("formats the same store currency and date for English and Arabic", () => {
    expect(formatCommerceMoney(12.5, "ILS", "en")).toContain("12.50");
    expect(formatCommerceMoney(12.5, "ILS", "ar")).toMatch(/١٢|12/);
    expect(formatCommerceDateTime("2026-01-02T10:00:00Z", "en")).not.toBe(formatCommerceDateTime("2026-01-02T10:00:00Z", "ar"));
  });
});
