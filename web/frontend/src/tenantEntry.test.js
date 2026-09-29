import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { getBrandedMadarSubdomain } from "./utils/hostedAddress";

const source = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

describe("hosted tenant entry boundary", () => {
  it("selects only branded tenant hosts", () => {
    expect(getBrandedMadarSubdomain("disco.madarportal.com")).toBe("disco");
    expect(getBrandedMadarSubdomain("app.madarportal.com")).toBe("");
    expect(getBrandedMadarSubdomain("madarportal.com")).toBe("");
    expect(getBrandedMadarSubdomain("disco.other.example")).toBe("");
  });

  it("keeps the application shell out of the tenant entry", () => {
    const entry = source("./main.jsx");
    const tenant = source("./tenantMain.jsx");
    expect(entry).toContain('import("./tenantMain.jsx")');
    expect(entry).toContain('import("./appMain.jsx")');
    expect(tenant).toContain('import TenantSiteRoutes from "./routes/TenantSiteRoutes"');
    expect(tenant).not.toContain('from "./App.jsx"');
  });

  it("keeps editor and dashboard styles out of the published renderer", () => {
    const entryStyles = source("./styles/tenant-entry.css");
    const rendererStyles = source("./styles/admin/PageBuilder/public-runtime.css");
    expect(entryStyles).not.toContain("admin/dashboard/index.css");
    expect(rendererStyles).not.toContain("./index.css");
    expect(source("./components/PageBuilder/runtime/TenantSiteRuntime.jsx"))
      .toContain('import "../../../styles/admin/PageBuilder/public-runtime.css"');
    expect(source("./components/PageBuilder/runtime/TenantSiteRuntime.jsx"))
      .toContain('from "../services/PageBuilder.publicApi"');
  });

  it("keeps ecommerce and standalone forms behind their existing routes", () => {
    const routes = source("./routes/TenantSiteRoutes.jsx");
    expect(routes).toContain('import("../components/EcommerceStore/EcommerceStorefront")');
    expect(routes).toContain('path="/forms/:formId"');
    expect(routes).toContain('path="/*"');
  });
});
