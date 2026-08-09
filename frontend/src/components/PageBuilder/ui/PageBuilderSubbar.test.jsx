import { fireEvent, render, screen } from "@testing-library/react";
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
        copy={{ preview: "Preview" }}
        onPreviewClick={vi.fn()}
      />
    );

    expect(screen.getByRole("toolbar", { name: "Artboard zoom" })
      .closest(".builder-subbar-actions")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Preview" })).toBeNull();
  });

  it("keeps the existing exit control while preview is active", () => {
    const onPreviewClick = vi.fn();

    render(
      <PageBuilderSubbar
        preview
        hideWorkspaceTabs={false}
        viewports={{ desktop: 1200, mobile: 390 }}
        viewport="desktop"
        setViewport={vi.fn()}
        renderWorkspaceNavigator={() => null}
        copy={{ exitPreview: "Exit preview" }}
        onPreviewClick={onPreviewClick}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Exit preview" }));

    expect(onPreviewClick).toHaveBeenCalledTimes(1);
  });
});
