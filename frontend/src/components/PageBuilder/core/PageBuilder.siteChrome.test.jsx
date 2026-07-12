import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { createSiteChromeRenderers } from "./PageBuilder.siteChrome";

describe("site header navigation", () => {
  it("does not render pages hidden from the header", () => {
    const home = { id: "home", name: "Home", slug: "/", showInNavigation: true };
    const hidden = { id: "page_2", name: "Page 2", slug: "/page-2", showInNavigation: false };
    const { renderSiteHeader } = createSiteChromeRenderers({
      project: {
        pages: [home, hidden],
        siteChrome: { showHeader: true, brand: "Madar", headerButtonLabel: "Contact" },
      },
      activePage: hidden,
      selected: { type: "page" },
      preview: false,
      selectPage: vi.fn(),
      setSelected: vi.fn(),
    });

    render(renderSiteHeader());

    expect(screen.getByRole("button", { name: "Home" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Page 2" })).toBeNull();
  });
});
