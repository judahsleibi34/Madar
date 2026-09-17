import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import TenantSiteRoutes from "./TenantSiteRoutes";

vi.mock("../components/PageBuilder/runtime/TenantSiteRuntime", () => ({
  default: () => <div>Builder website runtime</div>,
}));

vi.mock("../components/EcommerceStore/EcommerceStorefront", () => ({
  default: () => <div>External ecommerce storefront</div>,
}));

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="current location">{`${location.pathname}${location.search}`}</output>;
}

describe("TenantSiteRoutes storefront connection", () => {
  it("mounts the standalone ecommerce storefront at the website Shop path", async () => {
    render(
      <MemoryRouter initialEntries={["/site/madar-demo/shop/catalog?tag=best-seller"]}>
        <TenantSiteRoutes />
        <LocationProbe />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText("current location").textContent).toBe(
        "/site/madar-demo/shop/catalog?tag=best-seller"
      );
    });
    expect(await screen.findByText("External ecommerce storefront")).toBeTruthy();
    expect(screen.queryByText("Builder website runtime")).toBeNull();
  });
});
