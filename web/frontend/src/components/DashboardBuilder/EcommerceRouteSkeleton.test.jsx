import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import EcommerceRouteSkeleton from "./EcommerceRouteSkeleton";

afterEach(cleanup);

describe("EcommerceRouteSkeleton", () => {
  it.each([
    ["/ecommerce/tags", ".ecommerce-page-skeleton"],
    ["/ecommerce/categories", ".ecommerce-page-skeleton"],
    ["/ecommerce/products", ".ecommerce-page-skeleton"],
    ["/ecommerce/products/new", ".commerce-editor-skeleton"],
    ["/ecommerce/products/product-1/edit", ".commerce-editor-skeleton"],
    ["/ecommerce/delivery", ".ecommerce-skeleton-delivery-grid"],
    ["/ecommerce/orders", ".ecommerce-skeleton-order-list"],
    ["/ecommerce/loyalty", ".ecommerce-skeleton-field-grid"],
    ["/ecommerce/theme", ".ecommerce-theme-skeleton"],
    ["/ecommerce/store", ".ecommerce-store-page-skeleton"],
  ])("renders a page-shaped fallback for %s", (pathname, selector) => {
    const { container } = render(<EcommerceRouteSkeleton pathname={pathname} label="Loading Online Store" />);
    expect(screen.getByRole("status", { name: "Loading Online Store" })).toBeTruthy();
    expect(container.querySelector(selector)).toBeTruthy();
  });

  it("renders the order-detail structure for an order URL", () => {
    const { container } = render(<EcommerceRouteSkeleton pathname="/ecommerce/orders/order-1" label="Loading order" />);
    expect(container.querySelector(".ecommerce-skeleton-detail-grid")).toBeTruthy();
  });
});
