import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PageBuilderThemeTab from "./PageBuilderThemeTab";

afterEach(() => {
  cleanup();
});

describe("PageBuilderThemeTab builder theme controls", () => {
  it("shows builder colors without rendering form color controls", () => {
    render(
      <PageBuilderThemeTab
        project={{ theme: { background: "#123456", surface: "#234567", form: {} } }}
        updateProject={vi.fn()}
        saveProject={vi.fn()}
      />
    );

    expect(screen.getByLabelText("Site background").value).toBe("#123456");
    expect(screen.getByLabelText("Content area").value).toBe("#234567");
    expect(screen.queryByLabelText("Form page")).toBeNull();
    expect(screen.queryByLabelText("Form card")).toBeNull();
  });

  it("updates builder colors without changing saved form colors", () => {
    const updateProject = vi.fn();
    const project = {
      theme: {
        background: "#123456",
        surface: "#234567",
        form: { surface: "#ffffff" },
      },
    };

    render(
      <PageBuilderThemeTab
        project={project}
        updateProject={updateProject}
        saveProject={vi.fn()}
      />
    );

    fireEvent.change(screen.getByLabelText("Site background"), {
      target: { value: "#abcdef" },
    });

    const updater = updateProject.mock.calls[0][0];
    const nextProject = updater(project);

    expect(nextProject.theme.background).toBe("#abcdef");
    expect(nextProject.theme.surface).toBe("#234567");
    expect(nextProject.theme.form.surface).toBe("#ffffff");
  });
});
