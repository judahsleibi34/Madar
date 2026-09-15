import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import EcommerceOperationsSkeleton from "./EcommerceOperationsSkeleton";

afterEach(cleanup);

describe("EcommerceOperationsSkeleton", () => {
  it("matches the delivery card grid", () => {
    const { container } = render(<EcommerceOperationsSkeleton variant="delivery" label="Loading delivery" />);
    expect(screen.getByRole("status", { name: "Loading delivery" })).toBeTruthy();
    expect(container.querySelectorAll(".ecommerce-skeleton-delivery-card")).toHaveLength(8);
  });

  it("matches the loyalty form grid", () => {
    const { container } = render(<EcommerceOperationsSkeleton variant="loyalty" label="Loading loyalty" />);
    expect(container.querySelectorAll(".ecommerce-skeleton-field-grid > div")).toHaveLength(8);
  });

  it("matches the orders table", () => {
    const { container } = render(<EcommerceOperationsSkeleton variant="orders" label="Loading orders" />);
    expect(container.querySelectorAll(".ecommerce-skeleton-order-row")).toHaveLength(5);
    expect(container.querySelectorAll(".ecommerce-skeleton-order-row:first-child > i")).toHaveLength(6);
  });

  it("matches the order detail layout", () => {
    const { container } = render(<EcommerceOperationsSkeleton variant="order-detail" label="Loading order" />);
    expect(container.querySelectorAll(".ecommerce-skeleton-detail-grid > div")).toHaveLength(4);
    expect(container.querySelector(".ecommerce-skeleton-detail-panel")).toBeTruthy();
  });
});
