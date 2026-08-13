import { describe, expect, it } from "vitest";

import { getRouteErrorSurface } from "./routes/routeErrorSurface";

describe("getRouteErrorSurface", () => {
  it.each([
    ["/", {}, "public"],
    ["/site/example", {}, "tenant-site"],
    ["/forms/example/contact", {}, "tenant-site"],
    ["/dashboard", {}, "user-workspace"],
    ["/dashboard", { isAdminUser: true }, "admin"],
    ["/page-builder/projects/one", {}, "page-builder"],
    ["/builder-data/projects/one", {}, "data-analysis"],
  ])("maps %s to %s", (pathname, options, expected) => {
    expect(getRouteErrorSurface(pathname, options)).toBe(expected);
  });
});
