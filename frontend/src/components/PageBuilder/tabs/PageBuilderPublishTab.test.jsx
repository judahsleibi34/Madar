import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PageBuilderPublishTab from "./PageBuilderPublishTab";

const project = {
  name: "Madar Site",
  status: "published",
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
      />
    );

    expect(screen.getByDisplayValue("http://localhost:3000/site/disco2/")).toBeTruthy();
    expect(screen.queryByDisplayValue(/project_/)).toBeNull();
  });

  it("does not invent a public URL when no subdomain is available", () => {
    render(<PageBuilderPublishTab project={project} />);

    expect(screen.getByPlaceholderText("Configure a website subdomain before sharing the live site.")).toBeTruthy();
    expect(screen.getByRole("button", { name: /copy link/i }).disabled).toBe(true);
    expect(screen.getByRole("button", { name: /preview site/i }).disabled).toBe(true);
  });

  it("does not show a publish action in the Publish tab", () => {
    render(<PageBuilderPublishTab project={project} liveSitePath="/site/disco2/" />);

    expect(screen.queryByRole("button", { name: /publish site|go live/i })).toBeNull();
  });

  it("opens the confirmed live site without writing browser recovery", () => {
    const persistProjectNow = vi.fn();
    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);

    render(
      <PageBuilderPublishTab
        project={project}
        liveSitePath="/site/disco2/"
        persistProjectNow={persistProjectNow}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: /preview site/i }));

    expect(openSpy).toHaveBeenCalledWith(
      "http://localhost:3000/site/disco2/",
      "_blank",
      "noopener,noreferrer"
    );
    expect(persistProjectNow).not.toHaveBeenCalled();
  });
});
