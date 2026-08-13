import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PageBuilderSubbar from "./PageBuilderSubbar";

describe("PageBuilderSubbar", () => {
  it("keeps artboard controls in the subbar action area", () => {
    render(
      <PageBuilderSubbar
        preview={false}
        hideWorkspaceTabs={false}
        viewports={{ desktop: 1200 }}
        viewport="desktop"
        setViewport={vi.fn()}
        renderWorkspaceNavigator={() => <nav>Pages</nav>}
        artboardCameraControls={<div role="toolbar" aria-label="Artboard zoom">Zoom</div>}
      />
    );

    expect(screen.getByRole("toolbar", { name: "Artboard zoom" })
      .closest(".builder-subbar-actions")).toBeTruthy();
  });

  it("keeps only viewport controls in the preview subbar", () => {
    render(
      <PageBuilderSubbar
        preview
        hideWorkspaceTabs={false}
        viewports={{ desktop: 1200, mobile: 390 }}
        viewport="desktop"
        setViewport={vi.fn()}
        renderWorkspaceNavigator={() => null}
      />
    );

    expect(screen.queryByRole("button", { name: "Exit preview" })).toBeNull();
    expect(screen.getByRole("button", { name: "desktop" })).toBeTruthy();
  });
});