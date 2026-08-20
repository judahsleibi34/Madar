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
    expect(variables["--theme-text"]).toBe("#000000");
  });

  it("isolates site action colors from the surrounding application theme", () => {
    const variables = getPageBuilderThemeVars({
      accent: "#2f7a58",
      accentDark: "#245e49",
      buttonText: "#ffe1e1",
    });

    expect(variables["--action-primary"]).toBe("#2f7a58");
    expect(variables["--action-primary-hover"]).toBe("#245e49");
    expect(variables["--theme-icon-background"]).toBe("#2f7a58");
    expect(variables["--theme-icon-foreground"]).toBe("#ffe1e1");
    expect(variables["--theme-on-primary"]).toBe("#ffe1e1");
    expect(variables["--theme-text-inverse"]).toBe("#ffe1e1");
  });

  it("exposes a dedicated header background color with a safe default", () => {
    expect(getPageBuilderThemeVars({ headerBackground: "#123456" })["--theme-header-background"])
      .toBe("#123456");
    expect(getPageBuilderThemeVars({ surface: "#abcdef", headerBackground: "" })["--theme-header-background"])
      .toBe("#abcdef");
  });
});
