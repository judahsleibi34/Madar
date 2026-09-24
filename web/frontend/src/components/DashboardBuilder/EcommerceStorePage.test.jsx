import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
    expect((await screen.findByTitle("Published online store")).getAttribute("src")).toBe("https://olive-house.madarportal.com/shop");
    fireEvent.load(screen.getByTitle("Published online store"));
    expect(screen.getByRole("link", { name: "Open production store" }).getAttribute("href")).toBe("https://olive-house.madarportal.com/shop");
    expect(screen.queryByText("Published storefront")).toBeNull();
    expect(screen.queryByText("Customer view")).toBeNull();
    expect(screen.queryByText("Live")).toBeNull();
    expect(container.querySelector(".ecommerce-store-frame-dot")).toBeNull();
  });

  it("passes the browser-only draft flag to the embedded preview", async () => {
    fetchWebsiteSettings.mockResolvedValue({ subdomain: "olive-house" });
    render(<MemoryRouter initialEntries={["/ecommerce/store?preview=draft"]}><EcommerceStorePage /></MemoryRouter>);

    expect((await screen.findByTitle("Draft online store preview")).getAttribute("src")).toBe("/ecommerce-preview/olive-house?preview=draft");
    fireEvent.load(screen.getByTitle("Draft online store preview"));
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

it("uses the same preview skeleton through settings and iframe loading, then removes it", async () => {
  let resolveSettings;
  fetchWebsiteSettings.mockReturnValue(new Promise(resolve => { resolveSettings = resolve; }));
  const { container } = render(<MemoryRouter><EcommerceStorePage /></MemoryRouter>);
  expect(container.querySelector(".commerce-preview-header")).toBeTruthy();
  expect(container.querySelector(".commerce-preview-hero")).toBeTruthy();
  expect(screen.queryByTitle("Published online store")).toBeNull();
  expect(screen.queryByRole("heading", { name: "Published store" })).toBeNull();
  expect(container.querySelector(".page-header-skeleton")).toBeTruthy();
  resolveSettings({ subdomain: "olive-house" });
  const iframe = await screen.findByTitle("Published online store");
  expect(container.querySelector(".ecommerce-store-frame-loading .commerce-preview-hero")).toBeTruthy();
  expect(screen.queryByRole("heading", { name: "Published store" })).toBeNull();
  expect(container.querySelector(".page-header-skeleton")).toBeTruthy();
  fireEvent.load(iframe);
  expect(screen.getByRole("heading", { name: "Published store" })).toBeTruthy();
  expect(container.querySelector(".page-header-skeleton")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(screen.queryByRole("heading", { name: "Published store" })).toBeNull();
  fireEvent.load(screen.getByTitle("Published online store"));
  expect(screen.getByRole("heading", { name: "Published store" })).toBeTruthy();
  expect(container.querySelector(".ecommerce-store-frame-loading")).toBeNull();
  expect(container.querySelector(".ecommerce-store-frame-shell").getAttribute("aria-busy")).toBe("false");
});
