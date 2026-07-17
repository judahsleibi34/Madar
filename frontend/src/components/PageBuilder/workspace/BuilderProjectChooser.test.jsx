import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import BuilderProjectChooser from "./BuilderProjectChooser";
import { listBuilderProjects } from "../services/PageBuilder.api";

vi.mock("../services/PageBuilder.api", () => ({
  createBuilderProject: vi.fn(),
  listBuilderProjects: vi.fn(),
}));

afterEach(cleanup);

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

describe("BuilderProjectChooser", () => {
  beforeEach(() => vi.clearAllMocks());

  it("presents a structured, accessible loading state while projects are fetched", () => {
    listBuilderProjects.mockReturnValue(new Promise(() => {}));
    const { container } = render(<MemoryRouter><BuilderProjectChooser /></MemoryRouter>);

    expect(screen.getByRole("status").textContent).toContain("Loading your projects");
    expect(screen.getByText("Loading projects...")).toBeTruthy();
    expect(container.querySelector(".builder-project-chooser").getAttribute("aria-busy")).toBe("true");
    expect(container.querySelectorAll(".builder-project-loading-row")).toHaveLength(3);
  });

  it("keeps two backend projects explicit and opens the selected one", async () => {
    listBuilderProjects.mockResolvedValue([
      { id: "project-a", name: "Alpha", status: "draft" },
      { id: "project-b", name: "Beta", status: "published" },
    ]);
    render(
      <MemoryRouter initialEntries={["/page-builder"]}>
        <BuilderProjectChooser />
        <LocationProbe />
      </MemoryRouter>
    );
    fireEvent.click((await screen.findByText("Beta")).closest("button"));
    expect(screen.getByTestId("location").textContent)
      .toBe("/page-builder/projects/project-b/pages");
  });

  it("does not expose archived projects omitted by the tenant-scoped backend list", async () => {
    listBuilderProjects.mockResolvedValue([{ id: "active", name: "Active", status: "draft" }]);
    render(<MemoryRouter><BuilderProjectChooser /></MemoryRouter>);
    expect(await screen.findByText("Active")).toBeTruthy();
    expect(screen.queryByText("Archived")).toBeNull();
  });

  it("redirects a legacy route with one project to its explicit URL", async () => {
    listBuilderProjects.mockResolvedValue([{ id: "only-project", name: "Only", status: "draft" }]);
    render(
      <MemoryRouter initialEntries={["/page-builder/pages"]}>
        <BuilderProjectChooser autoOpenSingleProject />
        <LocationProbe />
      </MemoryRouter>
    );
    expect((await screen.findByTestId("location")).textContent)
      .toBe("/page-builder/projects/only-project/pages");
    expect(screen.queryByText("Only")).toBeNull();
  });
});
