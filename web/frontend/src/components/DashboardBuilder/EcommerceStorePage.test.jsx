import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import EcommerceStorePage from "./EcommerceStorePage";
import { fetchWebsiteSettings } from "../PageBuilder/services/PageBuilder.api";

vi.mock("../PageBuilder/services/PageBuilder.api", () => ({
  fetchWebsiteSettings: vi.fn(),
}));

describe("EcommerceStorePage", () => {
  it("opens the storefront directly without an internal preview banner", async () => {
    fetchWebsiteSettings.mockResolvedValue({ subdomain: "olive-house" });

    const { container } = render(
      <MemoryRouter><EcommerceStorePage /></MemoryRouter>
    );
    expect((await screen.findByTitle("Published online store")).getAttribute("src")).toBe("/site/olive-house/shop");
    expect(screen.getByRole("link", { name: "Open production store" }).getAttribute("href")).toBe("https://madarportal.com/site/olive-house/shop");
    expect(screen.queryByText("Published storefront")).toBeNull();
    expect(screen.queryByText("Customer view")).toBeNull();
    expect(screen.queryByText("Live")).toBeNull();
    expect(container.querySelector(".ecommerce-store-frame-dot")).toBeNull();
  });

  it("passes the browser-only draft flag to the embedded preview", async () => {
    fetchWebsiteSettings.mockResolvedValue({ subdomain: "olive-house" });
    render(<MemoryRouter initialEntries={["/ecommerce/store?preview=draft"]}><EcommerceStorePage /></MemoryRouter>);

    expect((await screen.findByTitle("Draft online store preview")).getAttribute("src")).toBe("/site/olive-house/shop?preview=draft");
    expect(screen.getByText("Nothing here is live yet.", { exact: false })).toBeTruthy();
  });
});

afterEach(() => { cleanup(); vi.clearAllMocks(); });

it("shows safe toast and inline feedback when the store preview cannot load", async () => {
  fetchWebsiteSettings.mockRejectedValue(new Error("DATABASE_URL=secret; internal_settings SQL exception"));
  render(<MemoryRouter><EcommerceStorePage /></MemoryRouter>);
  expect((await screen.findByRole("alert")).textContent).toContain("Could not load website settings");
  expect(document.body.textContent).not.toContain("DATABASE_URL");
  expect(document.body.textContent).not.toContain("internal_settings");
});
