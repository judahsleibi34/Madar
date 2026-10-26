import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import BuilderProjectChooser from "./BuilderProjectChooser";
import { createBuilderProject, listBuilderProjects } from "../services/PageBuilder.api";

vi.mock("../services/PageBuilder.api", () => ({
  createBuilderProject: vi.fn(),
  listBuilderProjects: vi.fn(),
}));

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
});

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}</output>;
}

describe("BuilderProjectChooser", () => {
  beforeEach(() => vi.clearAllMocks());

  it("presents an accessible loading bar while projects are fetched", () => {
    listBuilderProjects.mockReturnValue(new Promise(() => {}));
    const { container } = render(<MemoryRouter><BuilderProjectChooser /></MemoryRouter>);

    expect(screen.getByRole("status").textContent).toContain("Loading your projects");
    expect(screen.getByText("Loading projects...")).toBeTruthy();
    expect(container.querySelector(".builder-project-chooser").getAttribute("aria-busy")).toBe("true");
    expect(container.querySelector(".app-loading-inline")).toBeTruthy();
    expect(container.querySelectorAll(".builder-project-loading-row")).toHaveLength(0);
  });

  it("shows a responsive Builder workspace preview while automatically entering a project", () => {
    listBuilderProjects.mockReturnValue(new Promise(() => {}));
    const { container } = render(
      <MemoryRouter><BuilderProjectChooser autoEnterProject /></MemoryRouter>
    );

    expect(screen.getByRole("status").textContent).toContain("Opening the Page Builder");
    expect(container.querySelector(".builder-project-loading-screen").getAttribute("aria-busy"))
      .toBe("true");
    expect(container.querySelector(".builder-project-loading-bar")).toBeTruthy();
    expect(container.querySelector(".app-loading-inline")).toBeTruthy();
    expect(container.querySelector(".builder-project-opening-preview")).toBeNull();
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
    await waitFor(() => expect(screen.getByTestId("location").textContent)
      .toBe("/page-builder/projects/only-project/pages"));
    expect(screen.queryByText("Only")).toBeNull();
  });

  it("enters the most recent project without showing the chooser", async () => {
    listBuilderProjects.mockResolvedValue({
      projects: [
        { id: "recent-project", name: "Recent", status: "draft" },
        { id: "older-project", name: "Older", status: "draft" },
      ],
      pagination: { limit: 20, offset: 0, count: 2, has_more: false },
    });
    render(
      <MemoryRouter initialEntries={["/page-builder"]}>
        <BuilderProjectChooser autoEnterProject />
        <LocationProbe />
      </MemoryRouter>
    );

    expect(screen.queryByText("Choose a project")).toBeNull();
    await waitFor(() => expect(screen.getByTestId("location").textContent)
      .toBe("/page-builder/projects/recent-project/pages"));
  });

  it("keeps normal Builder entry scoped to website projects", async () => {
    listBuilderProjects.mockResolvedValue({ projects: [{ id: "website", name: "Website" }], pagination: { has_more: false } });
    render(<MemoryRouter><BuilderProjectChooser autoEnterProject usageProfile="website" /><LocationProbe /></MemoryRouter>);
    await waitFor(() => expect(screen.getByTestId("location").textContent).toBe("/page-builder/projects/website/pages"));
    expect(listBuilderProjects).toHaveBeenCalledWith({ limit: 20, offset: 0, usageProfile: "website" });
    expect(createBuilderProject).not.toHaveBeenCalled();
  });

  it("lets the data workspace create a project root before entering its data leaf", async () => {
    listBuilderProjects.mockResolvedValue({
      projects: [],
      pagination: { limit: 20, offset: 0, count: 0, has_more: false },
    });
    createBuilderProject.mockResolvedValue({ id: "data-project-1" });

    render(
      <MemoryRouter initialEntries={["/builder-data"]}>
        <BuilderProjectChooser workspace="builder-data" usageProfile="website" />
        <LocationProbe />
      </MemoryRouter>
    );

    expect(await screen.findByRole("dialog", { name: "Choose a data project" })).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: /Create new project/i }));

    await waitFor(() => expect(screen.getByTestId("location").textContent)
      .toBe("/builder-data/projects/data-project-1/data"));
    expect(createBuilderProject).toHaveBeenCalledWith(expect.objectContaining({
      name: "My data project",
      draft_schema: expect.objectContaining({
        name: "My data project",
        workspaceKind: "data",
      }),
    }));
  });

  it("shows only projects created for the data workspace", async () => {
    listBuilderProjects.mockResolvedValue({
      projects: [
        { id: "form-project", name: "Form & Flow", slug: "form-and-flow", status: "published" },
        { id: "data-project", name: "Untitled data project", slug: "data-project-1729", status: "draft" },
        {
          id: "marked-data-project",
          name: "Customer research",
          slug: "customer-research",
          draft_schema: { workspaceKind: "data" },
        },
      ],
      pagination: { limit: 20, offset: 0, count: 3, has_more: false },
    });

    render(
      <MemoryRouter initialEntries={["/builder-data"]}>
        <BuilderProjectChooser workspace="builder-data" usageProfile="website" />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("button", { name: "My Projects" }));
    expect(await screen.findByText("My data project 1")).toBeTruthy();
    expect(screen.getByText("Customer research")).toBeTruthy();
    expect(screen.queryByText("Form & Flow")).toBeNull();
    expect(screen.queryByText("published")).toBeNull();
    expect(screen.queryByText("Data project")).toBeNull();
  });

  it("keeps data projects out of Submissions and opens the only form project", async () => {
    listBuilderProjects.mockResolvedValue({
      projects: [
        { id: "data-project", name: "Untitled data project", slug: "data-project-1729" },
        { id: "form-project", name: "Form & Flow", slug: "form-and-flow", status: "published" },
      ],
      pagination: { limit: 20, offset: 0, count: 2, has_more: false },
    });

    render(
      <MemoryRouter initialEntries={["/builder-responses"]}>
        <BuilderProjectChooser
          workspace="builder-responses"
          autoOpenSingleProject
          usageProfile="website"
        />
        <LocationProbe />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByTestId("location").textContent)
      .toBe("/builder-responses/projects/form-project/responses"));
    expect(screen.queryByText("Untitled data project")).toBeNull();
  });

  it("lets the user return to the dashboard from the data project popup", async () => {
    listBuilderProjects.mockResolvedValue({
      projects: [],
      pagination: { limit: 20, offset: 0, count: 0, has_more: false },
    });
    render(
      <MemoryRouter initialEntries={["/builder-data"]}>
        <BuilderProjectChooser workspace="builder-data" usageProfile="website" />
        <LocationProbe />
      </MemoryRouter>
    );

    const closeButton = await screen.findByRole("button", { name: "Back to dashboard" });
    const closeIcon = closeButton.querySelector("svg");
    expect(closeIcon?.getAttribute("width")).toBe("20");
    expect(closeIcon?.getAttribute("height")).toBe("20");
    expect(closeIcon?.getAttribute("stroke-width")).toBe("2");

    fireEvent.click(closeButton);
    expect(screen.getByTestId("location").textContent).toBe("/dashboard");
  });

  it("opens a selected project inside the separate Data Sources endpoint", async () => {
    listBuilderProjects.mockResolvedValue({
      projects: [{ id: "source-project", name: "Research", slug: "data-project-research" }],
      pagination: { limit: 20, offset: 0, count: 1, has_more: false },
    });
    render(
      <MemoryRouter initialEntries={["/data-sources"]}>
        <BuilderProjectChooser
          workspace="data-sources"
          usageProfile="website"
          dataProjectSelectionKey="selected-data-project"
        />
        <LocationProbe />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("button", { name: "My Projects" }));
    fireEvent.click((await screen.findByText("Research")).closest("button"));
    expect(screen.getByTestId("location").textContent)
      .toBe("/data-sources/projects/source-project/data");
    expect(window.sessionStorage.getItem("selected-data-project")).toBe("source-project");
  });

  it("opens a selected data project inside Business Intelligence", async () => {
    listBuilderProjects.mockResolvedValue({
      projects: [{ id: "bi-project", name: "Operations", slug: "data-project-operations" }],
      pagination: { limit: 20, offset: 0, count: 1, has_more: false },
    });
    render(
      <MemoryRouter initialEntries={["/business-intelligence"]}>
        <BuilderProjectChooser
          workspace="business-intelligence"
          usageProfile="website"
          dataProjectSelectionKey="selected-data-project"
        />
        <LocationProbe />
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole("button", { name: "My Projects" }));
    fireEvent.click((await screen.findByText("Operations")).closest("button"));
    expect(screen.getByTestId("location").textContent)
      .toBe("/business-intelligence/projects/bi-project/data");
    expect(window.sessionStorage.getItem("selected-data-project")).toBe("bi-project");
  });

  it("creates and enters a project automatically when none exists", async () => {
    listBuilderProjects.mockResolvedValue({
      projects: [],
      pagination: { limit: 20, offset: 0, count: 0, has_more: false },
    });
    createBuilderProject.mockResolvedValue({ id: "new-project" });
    render(
      <MemoryRouter initialEntries={["/page-builder"]}>
        <BuilderProjectChooser autoEnterProject />
        <LocationProbe />
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByTestId("location").textContent)
      .toBe("/page-builder/projects/new-project/pages"));
    expect(createBuilderProject).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Create a new project")).toBeNull();
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
