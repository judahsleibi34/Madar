import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

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
    expect((await screen.findByTitle("Live ecommerce store")).getAttribute("src")).toBe("/site/olive-house/shop");
    expect(screen.getByRole("link", { name: "Open live store" }).getAttribute("href")).toBe("https://madarportal.com/site/olive-house/shop");
    expect(screen.queryByText("Published storefront")).toBeNull();
    expect(screen.queryByText("Customer view")).toBeNull();
    expect(screen.queryByText("Live")).toBeNull();
    expect(container.querySelector(".ecommerce-store-frame-dot")).toBeNull();
  });
});
