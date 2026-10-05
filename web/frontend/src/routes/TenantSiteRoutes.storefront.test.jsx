import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import TenantSiteRoutes from "./TenantSiteRoutes";

afterEach(cleanup);

vi.mock("../utils/hostedAddress", async (importOriginal) => ({
  ...(await importOriginal()),
  getBrandedMadarSubdomain: () => "madar-demo",
}));

vi.mock("../components/PageBuilder/runtime/TenantSiteRuntime", () => ({
  default: ({ siteIdentifier }) => (
    <div>{`Builder website runtime:${siteIdentifier}`}</div>
  ),
}));

vi.mock("../components/EcommerceStore/EcommerceStorefront", () => ({
  default: () => <div>External ecommerce storefront</div>,
}));

vi.mock("../components/ELearning/ELearningAcademy", () => ({ default: ({ subdomain }) => <div>Academy:{subdomain}</div>, HostedAcademyLearning: ({ subdomain }) => <div>Learning:{subdomain}</div> }));

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="current location">{`${location.pathname}${location.search}`}</output>;
}

describe("TenantSiteRoutes storefront connection", () => {
  it("mounts the standalone ecommerce storefront at the website Shop path", async () => {
    render(
      <MemoryRouter initialEntries={["/shop/catalog?tag=best-seller"]}>
        <TenantSiteRoutes />
        <LocationProbe />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByLabelText("current location").textContent).toBe(
        "/shop/catalog?tag=best-seller"
      );
    });
    expect(await screen.findByText("External ecommerce storefront")).toBeTruthy();
    expect(screen.queryByText("Builder website runtime:madar-demo")).toBeNull();
  });

  it("mounts the hosted storefront home at /shop without changing the path", async () => {
    render(<MemoryRouter initialEntries={["/shop"]}><TenantSiteRoutes /><LocationProbe /></MemoryRouter>);
    expect(await screen.findByText("External ecommerce storefront")).toBeTruthy();
    expect(screen.getByLabelText("current location").textContent).toBe("/shop");
  });

  it.each(["/", "/about/team", "/forms/contact-form"])(
    "renders the host-derived tenant runtime directly at %s without rewriting the path",
    async (path) => {
      render(
        <MemoryRouter initialEntries={[path]}>
          <TenantSiteRoutes />
          <LocationProbe />
        </MemoryRouter>
      );

      expect(await screen.findByText("Builder website runtime:madar-demo")).toBeTruthy();
      expect(screen.getByLabelText("current location").textContent).toBe(path);
    }
  );
});


it("mounts the fixed Academy and learner runtime on the existing tenant host", async () => {
  const view = render(<MemoryRouter initialEntries={["/academy/courses"]}><TenantSiteRoutes /></MemoryRouter>);
  expect(await screen.findByText("Academy:madar-demo")).toBeTruthy();
  view.unmount();
  render(<MemoryRouter initialEntries={["/my-learning/courses/course/lessons/lesson"]}><TenantSiteRoutes /></MemoryRouter>);
  expect(await screen.findByText("Learning:madar-demo")).toBeTruthy();
  expect(screen.queryByText("Builder website runtime:madar-demo")).toBeNull();
});
