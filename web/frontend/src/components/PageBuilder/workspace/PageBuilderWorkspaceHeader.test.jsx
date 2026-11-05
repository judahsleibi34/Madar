// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import PageBuilderWorkspaceHeader from "./PageBuilderWorkspaceHeader";

afterEach(cleanup);

const props = {
  builderCopy: { topbar: {} },
  project: { name: "Project" }, displayName: "Project", activeHelper: "Manage bookings",
  preview: false, hideWorkspaceTabs: false, viewports: { desktop: 1200 }, viewport: "desktop", setViewport: vi.fn(),
  renderWorkspaceNavigator: () => <nav aria-label="Builder workspaces"><a href="/pages">Pages</a><a href="/chrome">Header &amp; Footer</a><a href="/publish">Publish</a></nav>,
  historyControls: <div role="toolbar" aria-label="Edit history"><button>Undo</button><button>Redo</button></div>,
};

describe("PageBuilderWorkspaceHeader navigation", () => {
  it("keeps reservations in its own flow without a page-builder bar", () => {
    const { container } = render(<PageBuilderWorkspaceHeader {...props} activeTab="reservations" />);
    expect(screen.queryByRole("navigation", { name: "Builder workspaces" })).toBeNull();
    expect(container.querySelector('.builder-subbar')).toBeNull();
    expect(screen.getByRole("toolbar", { name: "Edit history" }).closest('.builder-topbar')).toBeTruthy();
    expect(screen.getByRole("button", { name: "Undo" })).toBeTruthy();
  });
  it.each(["design", "chrome", "publish"])("preserves page navigation in the %s flow", activeTab => {
    render(<PageBuilderWorkspaceHeader {...props} activeTab={activeTab} />);
    expect(screen.getByRole("navigation", { name: "Builder workspaces" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Pages" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Header & Footer" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Publish" })).toBeTruthy();
  });
});
