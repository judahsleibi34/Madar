// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import PageSkeleton from "./PageSkeleton";

afterEach(cleanup);

describe("PageSkeleton branded loading visual", () => {
  it("renders the tenant image eagerly on first paint", () => {
    const { container } = render(
      <PageSkeleton
        label="Loading Form & Flow"
        variant="tenant-runtime"
        brand="Form & Flow"
        imageUrl="/form-flow-pilates-loading.jpg"
      />
    );

    expect(screen.getByText("Form & Flow")).toBeTruthy();
    expect(container.querySelector(".page-skeleton-site-header")).toBeTruthy();
    expect(container.querySelector(".page-skeleton-site-hero")).toBeTruthy();
    expect(container.querySelectorAll(".page-skeleton-site-cards > i")).toHaveLength(3);
    const image = container.querySelector("img");
    expect(image.getAttribute("src")).toBe("/form-flow-pilates-loading.jpg");
    expect(image.getAttribute("loading")).toBe("eager");
    expect(image.getAttribute("fetchpriority")).toBe("high");
    expect(container.querySelector("main").getAttribute("dir")).toBe("ltr");
  });
});
