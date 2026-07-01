import { describe, expect, it } from "vitest";
import { defaultFormTheme, getPageBuilderThemeVars } from "./PageBuilder.theme";

describe("getPageBuilderThemeVars form colors", () => {
  it("keeps form defaults separate from website colors", () => {
    const vars = getPageBuilderThemeVars({
      background: "#123456",
      surface: "#234567",
      text: "#345678",
      muted: "#456789",
      accent: "#567890",
      buttonText: "#678901",
      form: {},
    });

    expect(vars["--theme-bg"]).toBe("#123456");
    expect(vars["--form-theme-bg"]).toBe(defaultFormTheme.background);
    expect(vars["--form-theme-surface"]).toBe(defaultFormTheme.surface);
    expect(vars["--form-theme-input"]).toBe(defaultFormTheme.inputBackground);
    expect(vars["--form-theme-text"]).toBe(defaultFormTheme.text);
    expect(vars["--form-theme-accent"]).toBe(defaultFormTheme.accent);
  });

  it("uses explicit form colors when they are set", () => {
    const vars = getPageBuilderThemeVars({
      background: "#123456",
      form: {
        background: "#abcdef",
        surface: "#fedcba",
        inputBackground: "#102030",
        text: "#203040",
        muted: "#304050",
        border: "#405060",
        accent: "#506070",
        buttonText: "#607080",
      },
    });

    expect(vars["--form-theme-bg"]).toBe("#abcdef");
    expect(vars["--form-theme-surface"]).toBe("#fedcba");
    expect(vars["--form-theme-input"]).toBe("#102030");
    expect(vars["--form-theme-text"]).toBe("#203040");
    expect(vars["--form-theme-muted"]).toBe("#304050");
    expect(vars["--form-theme-border"]).toBe("#405060");
    expect(vars["--form-theme-accent"]).toBe("#506070");
    expect(vars["--form-theme-button-text"]).toBe("#607080");
  });
});
