import { describe, expect, it } from "vitest";

import { getPageBuilderThemeVars } from "./PageBuilder.theme";

describe("Page Builder typography theme", () => {
  it("exposes the selected font as both an inherited style and shared runtime token", () => {
    const variables = getPageBuilderThemeVars({ fontFamily: "Times New Roman" });

    expect(variables.fontFamily).toContain('"Times New Roman"');
    expect(variables.fontFamily).toContain("system-ui");
    expect(variables["--theme-font-family"]).toBe(variables.fontFamily);
  });

  it("uses the same Inter fallback when no font is configured", () => {
    const variables = getPageBuilderThemeVars({});

    expect(variables.fontFamily).toContain('"Inter"');
    expect(variables.fontFamily).toContain('"IBM Plex Sans Arabic"');
    expect(variables["--theme-font-family"]).toBe(variables.fontFamily);
  });
});
