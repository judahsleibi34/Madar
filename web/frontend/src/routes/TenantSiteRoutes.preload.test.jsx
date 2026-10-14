import { act, cleanup, render, screen } from "@testing-library/react";
import { lazy } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import RouteSuspense from "../components/common/RouteSuspense";

const preload = vi.hoisted(() => ({ loaded: {}, pending: {}, load: vi.fn() }));

vi.mock("../utils/hostedAddress", async (importOriginal) => ({
  ...(await importOriginal()),
  getBrandedMadarSubdomain: () => "madar-demo",
}));

vi.mock("../tenantRuntimePreload", () => ({
  getLoadedTenantRouteModule: (kind) => preload.loaded[kind] || null,
  getPendingTenantRouteModule: (kind) => preload.pending[kind] || null,
  loadTenantRouteModule: preload.load,
  ROUTE_TRANSLATION_NAMESPACES: {
    site: ["common", "dashboard"],
    store: ["common", "commerce"],
  },
}));

vi.mock("../components/ELearning/ELearningAcademy", () => ({ default: () => null, HostedAcademyLearning: () => null }));

const { default: TenantSiteRoutes } = await import("./TenantSiteRoutes");

const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
};

const suspenseFallbackMarkup = () => {
  const Never = lazy(() => new Promise(() => {}));
  const view = render(
    <RouteSuspense label="Loading site" variant="tenant-runtime" delay={0}>
      <Never />
    </RouteSuspense>
  );
  const markup = view.container.innerHTML;
  view.unmount();
  return markup;
};

describe("TenantSiteRoutes entry preload hand-off", () => {
  beforeEach(() => {
    preload.loaded = {};
    preload.pending = {};
    preload.load.mockReset();
  });
  afterEach(cleanup);

  it("shows the unchanged route skeleton while the preload is in flight, then the route", async () => {
    const expectedSkeleton = suspenseFallbackMarkup();
    const site = deferred();
    preload.pending.site = site.promise;

    const view = render(<MemoryRouter initialEntries={["/about"]}><TenantSiteRoutes /></MemoryRouter>);
    expect(view.container.innerHTML).toBe(expectedSkeleton);

    await act(async () => site.resolve({ default: ({ siteIdentifier }) => <div>{`Runtime:${siteIdentifier}`}</div> }));
    expect(screen.getByText("Runtime:madar-demo")).toBeTruthy();
    expect(view.container.querySelector(".page-skeleton")).toBeNull();
    expect(preload.load).not.toHaveBeenCalled();
  });

  it("falls back to the route's lazy loader when the preload fails", async () => {
    const store = deferred();
    preload.pending.store = store.promise;
    preload.load.mockResolvedValue({ default: () => <div>Storefront</div> });

    render(<MemoryRouter initialEntries={["/shop"]}><TenantSiteRoutes /></MemoryRouter>);
    await act(async () => store.reject(new Error("chunk failed")));

    expect(await screen.findByText("Storefront")).toBeTruthy();
    expect(preload.load).toHaveBeenCalledWith("store");
  });
});
