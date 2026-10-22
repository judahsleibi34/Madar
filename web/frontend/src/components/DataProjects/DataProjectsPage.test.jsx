import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import DataProjectsPage from "./DataProjectsPage";
import {
  createBuilderProject,
  listBuilderProjects,
} from "../PageBuilder/services/PageBuilder.api";

vi.mock("../PageBuilder/services/PageBuilder.api", () => ({
  createBuilderProject: vi.fn(),
  listBuilderProjects: vi.fn(),
}));

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

afterEach(cleanup);

describe("DataProjectsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listBuilderProjects.mockResolvedValue({
      projects: [
        { id: "form-1", name: "Form & Flow", slug: "form-and-flow" },
        { id: "data-1", name: "Sales analysis", slug: "data-project-100" },
      ],
      pagination: { has_more: false },
    });
  });

  it("renders a standalone panel containing only data projects", async () => {
    render(
      <MemoryRouter initialEntries={["/data-projects"]}>
        <DataProjectsPage />
        <LocationProbe />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "Projects", level: 1 })).toBeTruthy();
    expect(screen.getByText("Sales analysis")).toBeTruthy();
    expect(screen.queryByText("Form & Flow")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Back to dashboard" }));
    expect(screen.getByTestId("location").textContent).toBe("/dashboard");
  });

  it("creates a named project from the default modal and opens its Data Logs workspace", async () => {
    createBuilderProject.mockResolvedValue({ id: "data-2" });
    render(
      <MemoryRouter initialEntries={["/data-projects"]}>
        <DataProjectsPage />
        <LocationProbe />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("button", { name: "New project" }));
    const dialog = screen.getByRole("dialog", { name: "Create a data project" });
    fireEvent.change(screen.getByRole("textbox", { name: "Project name" }), {
      target: { value: "Customer research" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    await waitFor(() => expect(screen.getByTestId("location").textContent)
      .toBe("/builder-data/projects/data-2/data"));
    expect(dialog).toBeTruthy();
    expect(createBuilderProject).toHaveBeenCalledWith(expect.objectContaining({
      name: "Customer research",
      draft_schema: expect.objectContaining({
        name: "Customer research",
        workspaceKind: "data",
      }),
    }));
  });
});
