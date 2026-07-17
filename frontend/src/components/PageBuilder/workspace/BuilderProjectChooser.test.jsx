import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
    listBuilderProjects.mockResolvedValue({
      projects: [
        { id: "project-a", name: "Alpha", status: "draft" },
        { id: "project-b", name: "Beta", status: "published" },
      ],
      pagination: { limit: 20, offset: 0, count: 2, has_more: false },
    });
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
    listBuilderProjects.mockResolvedValue({
      projects: [{ id: "active", name: "Active", status: "draft" }],
      pagination: { limit: 20, offset: 0, count: 1, has_more: false },
    });
    render(<MemoryRouter><BuilderProjectChooser /></MemoryRouter>);
    expect(await screen.findByText("Active")).toBeTruthy();
    expect(screen.queryByText("Archived")).toBeNull();
  });

  it("redirects a legacy route with one project to its explicit URL", async () => {
    listBuilderProjects.mockResolvedValue({
      projects: [{ id: "only-project", name: "Only", status: "draft" }],
      pagination: { limit: 20, offset: 0, count: 1, has_more: false },
    });
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

  it("loads projects beyond the first twenty without duplicating records", async () => {
    const firstPage = Array.from({ length: 20 }, (_, index) => ({
      id: `project-${index + 1}`,
      name: `Project ${index + 1}`,
      status: "draft",
    }));
    listBuilderProjects
      .mockResolvedValueOnce({
        projects: firstPage,
        pagination: { limit: 20, offset: 0, count: 20, has_more: true },
      })
      .mockResolvedValueOnce({
        projects: [firstPage[19], { id: "project-21", name: "Project 21", status: "draft" }],
        pagination: { limit: 20, offset: 20, count: 2, has_more: false },
      });

    render(<MemoryRouter><BuilderProjectChooser /></MemoryRouter>);
    fireEvent.click(await screen.findByText("Load more projects"));

    expect(await screen.findByText("Project 21")).toBeTruthy();
    await waitFor(() => expect(screen.queryByText("Load more projects")).toBeNull());
    expect(screen.getAllByText("Project 20")).toHaveLength(1);
    expect(listBuilderProjects).toHaveBeenNthCalledWith(1, { limit: 20, offset: 0 });
    expect(listBuilderProjects).toHaveBeenNthCalledWith(2, { limit: 20, offset: 20 });
  });

  it("keeps loaded projects visible when loading another page fails", async () => {
    listBuilderProjects
      .mockResolvedValueOnce({
        projects: [{ id: "project-1", name: "Project 1", status: "draft" }],
        pagination: { limit: 20, offset: 0, count: 1, has_more: true },
      })
      .mockRejectedValueOnce(new Error("network"));

    render(<MemoryRouter><BuilderProjectChooser /></MemoryRouter>);
    fireEvent.click(await screen.findByText("Load more projects"));

    expect((await screen.findByRole("alert")).textContent).toContain(
      "More projects could not be loaded"
    );
    expect(screen.getByText("Project 1")).toBeTruthy();
  });
});
