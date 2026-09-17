import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PageBuilderTopbar from "./PageBuilderTopbar";

describe("PageBuilderTopbar", () => {
  it("keeps project identity in the header without duplicating sidebar save controls", () => {
    render(
      <PageBuilderTopbar
        project={{ name: "Site" }}
        activeHelper="Build pages"
      />
    );

    expect(screen.getByRole("heading", { name: "Site" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Save$/i })).toBeNull();
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("keeps project identity out of the heading hierarchy when a nested page owns the H1", () => {
    const view = render(
      <PageBuilderTopbar
        project={{ name: "Site" }}
        activeHelper="Review responses"
        activeTab="responses"
      />
    );

    expect(view.container.querySelector("h1")).toBeNull();
    expect(view.container.querySelector(".builder-brand-name")?.tagName).toBe("SPAN");
  });
  it("places the exit preview action in the header", () => {
    const onPreviewClick = vi.fn();

    render(
      <PageBuilderTopbar
        project={{ name: "Site" }}
        activeHelper="Build pages"
        preview
        copy={{ exitPreview: "Exit site preview" }}
        onPreviewClick={onPreviewClick}
      />
    );

    const exitButton = screen.getByRole("button", { name: "Exit site preview" });
    expect(exitButton.closest(".builder-topbar")).toBeTruthy();
    expect(exitButton.classList.contains("primary-action")).toBe(true);

    fireEvent.click(exitButton);
    expect(onPreviewClick).toHaveBeenCalledTimes(1);
  });
});