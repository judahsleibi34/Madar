import { describe, expect, it } from "vitest";

import { getPageBuilderThemeVars } from "./PageBuilder.theme";

describe("Page Builder typography theme", () => {
  it("exposes the selected font as both an inherited style and shared runtime token", () => {
    const variables = getPageBuilderThemeVars({ fontFamily: "Times New Roman" });

    expect(variables.fontFamily).toBe("Times New Roman");
    expect(variables["--theme-font-family"]).toBe("Times New Roman");
  });

  it("uses the same Inter fallback when no font is configured", () => {
    const variables = getPageBuilderThemeVars({});

    expect(variables.fontFamily).toBe("Inter");
    expect(variables["--theme-font-family"]).toBe("Inter");
  });
});
