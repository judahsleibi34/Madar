import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PageBuilderThemeTab from "./PageBuilderThemeTab";

afterEach(() => {
  cleanup();
});

describe("PageBuilderThemeTab form theme controls", () => {
  it("shows form color defaults instead of inheriting website colors", () => {
    render(
      <PageBuilderThemeTab
        project={{ theme: { background: "#123456", surface: "#234567", form: {} } }}
        updateProject={vi.fn()}
        saveProject={vi.fn()}
      />
    );

    expect(screen.getByLabelText("Site background").value).toBe("#123456");
    expect(screen.getByLabelText("Form page").value).toBe("#ffffff");
    expect(screen.getByLabelText("Form card").value).toBe("#ffffff");
  });

  it("updates form colors without changing website colors", () => {
    const updateProject = vi.fn();
    const project = {
      theme: {
        background: "#123456",
        surface: "#234567",
        form: { background: "#ffffff" },
      },
    };

    render(
      <PageBuilderThemeTab
        project={project}
        updateProject={updateProject}
        saveProject={vi.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText("Form page"), {
      target: { value: "#abcdef" },
    });

    const updater = updateProject.mock.calls[0][0];
    const nextProject = updater(project);

    expect(nextProject.theme.background).toBe("#123456");
    expect(nextProject.theme.form.background).toBe("#abcdef");
  });
});
