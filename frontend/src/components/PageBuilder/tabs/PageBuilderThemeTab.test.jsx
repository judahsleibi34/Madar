import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import PageBuilderThemeTab from "./PageBuilderThemeTab";

afterEach(cleanup);

describe("PageBuilderThemeTab sidebar", () => {
  it("presents the theme controls in semantic groups and preserves a zero radius", () => {
    const updateProject = vi.fn();

    const { container } = render(
      <PageBuilderThemeTab
        project={{ theme: { radius: 0, fontFamily: "Inter" } }}
        updateProject={updateProject}
        variant="sidebar"
      />
    );

    expect(container.querySelector(".page-utility-actions.theme-sidebar-actions")).toBeTruthy();
    expect(container.querySelector(".section-component-palette.theme-sidebar-palette")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Themes" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Theme colors" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Shape & typography" })).toBeTruthy();
    expect(screen.getByLabelText("Corner radius").value).toBe("0");
    expect(screen.getByRole("button", { name: "Apply to pages" })).toBeTruthy();
  });

  it("keeps form styling when the website theme is reset", () => {
    const updateProject = vi.fn();
    render(
      <PageBuilderThemeTab
        project={{ theme: { radius: 4, form: { accent: "#123456" } } }}
        updateProject={updateProject}
        variant="sidebar"
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    const resetProject = updateProject.mock.calls[0][0];
    const result = resetProject({ theme: { radius: 4, form: { accent: "#123456" } } });

    expect(result.theme.form).toEqual({ accent: "#123456" });
    expect(result.theme.radius).not.toBe(4);
  });

  it("allows theme colors to be edited as hexadecimal values", () => {
    const updateProject = vi.fn();
    const initialBackground = ["#", "ABCDEF"].join("");
    render(
      <PageBuilderThemeTab
        project={{ theme: { background: initialBackground } }}
        updateProject={updateProject}
        variant="sidebar"
      />
    );

    const hexInput = screen.getByLabelText("Site background hex");
    expect(hexInput.value).toBe("#ABCDEF");
    fireEvent.change(hexInput, { target: { value: "#123456" } });

    const updater = updateProject.mock.calls.at(-1)[0];
    expect(updater({ theme: { background: initialBackground } }).theme.background).toBe("#123456");
    expect(screen.getByLabelText("Site background color picker")).toBeTruthy();
  });
});
