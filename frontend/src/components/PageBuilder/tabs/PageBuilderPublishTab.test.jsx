import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PageBuilderPublishTab from "./PageBuilderPublishTab";

const project = {
  name: "Madar Site",
  status: "draft",
  publish: {},
  forms: [],
};

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("PageBuilderPublishTab", () => {
  it("uses the canonical tenant subdomain live path", () => {
    render(
      <PageBuilderPublishTab
        project={project}
        liveSitePath="/site/disco2/"
        publishProject={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue("http://localhost:3000/site/disco2/")).toBeTruthy();
    expect(screen.queryByDisplayValue(/project_/)).toBeNull();
  });

  it("falls back to the configured publish subdomain while website settings load", () => {
    render(
      <PageBuilderPublishTab
        project={{
          ...project,
          publish: {
            subdomain: "disco2",
          },
        }}
        publishProject={vi.fn()}
      />
    );

    expect(screen.getByDisplayValue("http://localhost:3000/site/disco2/")).toBeTruthy();
    expect(screen.queryByDisplayValue(/project_/)).toBeNull();
  });

  it("does not invent a public URL when no subdomain is available", () => {
    render(<PageBuilderPublishTab project={project} publishProject={vi.fn()} />);

    expect(screen.getByPlaceholderText("Configure a website subdomain before sharing the live site.")).toBeTruthy();
    expect(screen.getByRole("button", { name: /copy link/i }).disabled).toBe(true);
    expect(screen.getByRole("button", { name: /preview site/i }).disabled).toBe(true);
  });

  it("calls publishProject from the publish action", async () => {
    const publishProject = vi.fn().mockResolvedValue(undefined);

    render(
      <PageBuilderPublishTab
        project={project}
        liveSitePath="/site/disco2/"
        publishProject={publishProject}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /publish site/i }));

    await waitFor(() => expect(publishProject).toHaveBeenCalledTimes(1));
  });

  it("preview site does not call publishProject", () => {
    const publishProject = vi.fn();
    const persistProjectNow = vi.fn();

    render(
      <PageBuilderPublishTab
        project={project}
        liveSitePath="/site/disco2/"
        publishProject={publishProject}
        persistProjectNow={persistProjectNow}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /preview site/i }));

    expect(publishProject).not.toHaveBeenCalled();
    expect(persistProjectNow).toHaveBeenCalledTimes(1);
  });
});
