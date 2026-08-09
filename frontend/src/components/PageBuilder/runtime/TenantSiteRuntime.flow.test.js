import { describe, expect, it } from "vitest";
import {
  cacheTenantBrand,
  getRuntimeAuthFlow,
  getVerifiedPublicationBoundary,
  getTenantBrandFallback,
  getTenantLoadingLogoUrl,
  getRuntimeCanvasScale,
  getRuntimeDirectPosition,
  getRuntimeDirectElements,
  readCachedTenantBrand,
  getRuntimeViewportForWidth,
  getRuntimeNavigationPages,
  getRuntimePageSections,
  getSafeProtectedReturnPath,
  resolveRuntimePage,
  runtimePageRequiresAuthentication,
} from "./TenantSiteRuntime";

const loginPage = {
  id: "login-page",
  slug: "/",
  visibility: "public",
  sections: [{
    freeElements: [{
      id: "login",
      type: "loginBlock",
      auth: { successPageId: "form-page" },
    }],
    rows: [],
  }],
};

const formPage = {
  id: "form-page",
  slug: "/from",
  visibility: "public",
  sections: [],
};

describe("tenant brand loading", () => {
  it("caches a bounded tenant identity and restores it for repeat visits", () => {
    const values = new Map();
    const storage = {
      getItem: (key) => values.get(key) || null,
      setItem: (key, value) => values.set(key, value),
    };

    const boundary = {
      hostname: "madarportal.com",
      siteIdentifier: "madar-demo",
      siteId: "site-1",
      projectId: "project-1",
      publishedVersion: 4,
    };
    cacheTenantBrand(storage, boundary, {
      brand: "Madar Demo",
      logoUrl: "/uploads/tenant_1/builder_assets/1234567890abcdef1234567890abcdef.png",
      loadingImageUrl: "/uploads/tenant_1/builder_assets/loading.png",
    });

    expect(readCachedTenantBrand(storage, boundary)).toEqual({
      brand: "Madar Demo",
      logoUrl: "/uploads/tenant_1/builder_assets/1234567890abcdef1234567890abcdef.png",
      loadingImageUrl: "/uploads/tenant_1/builder_assets/loading.png",
    });
    expect(getTenantBrandFallback("madar-demo")).toBe("Madar Demo");
  });

  it("ignores malformed cached branding", () => {
    expect(readCachedTenantBrand({ getItem: () => "not-json" }, {
      hostname: "madarportal.com",
      siteIdentifier: "broken",
      siteId: "site-1",
      projectId: "project-1",
      publishedVersion: 1,
    })).toBeNull();
  });

  it("does not reuse branding without the complete publication boundary", () => {
    expect(readCachedTenantBrand({ getItem: () => "{}" }, "madar-demo")).toBeNull();
  });
});

describe("public publication boundary", () => {
  it("accepts only matching site and project identities", () => {
    const payload = {
      site: { subdomain: "alpha", site_id: "site-1", project_id: "project-1" },
      project: {
        site_id: "site-1",
        site_identifier: "alpha",
        project_id: "project-1",
        published_version: 4,
        publication_key: "site-1:alpha:project-1:4:hash",
      },
    };
    expect(getVerifiedPublicationBoundary(payload, "alpha", "madarportal.com"))
      .toMatchObject({ siteId: "site-1", projectId: "project-1", publishedVersion: 4 });
    expect(getVerifiedPublicationBoundary(payload, "beta", "madarportal.com")).toBeNull();
    expect(getVerifiedPublicationBoundary({
      ...payload,
      project: { ...payload.project, site_id: "" },
    }, "alpha", "madarportal.com")).toBeNull();
  });

  it("prioritizes the Website Settings logo while loading", () => {
    expect(getTenantLoadingLogoUrl({
      settingsLogoUrl: "/uploads/settings-logo.png",
      logoUrl: "/uploads/project-logo.png",
      loadingImageUrl: "/uploads/legacy-loader.png",
    })).toBe("/uploads/settings-logo.png");
  });
});

describe("tenant runtime page flow", () => {
  it("fits a logical canvas to the complete available browser width", () => {
    expect(getRuntimeCanvasScale(1000, 1200)).toBeCloseTo(5 / 6);
    expect(getRuntimeCanvasScale(390, 390)).toBe(1);
    expect(getRuntimeCanvasScale(600, 390)).toBe(1);
    expect(getRuntimeCanvasScale(1024, 768)).toBe(1);
    expect(getRuntimeCanvasScale(1600, 1200)).toBe(1);
  });

  it("normalizes missing breakpoint geometry from the nearest saved layout", () => {
    const position = getRuntimeDirectPosition({
      position: { desktop: { x: 120, y: 240, width: 600, height: 300 } },
    }, "mobile");

    expect(position).toEqual({ x: 39, y: 78, width: 195, height: 97.5 });
  });

  it("preserves authored element order at every breakpoint", () => {
    const elements = [
      { id: "image", position: { mobile: { x: 12, y: 420 } } },
      { id: "text", position: { mobile: { x: 12, y: 180 } } },
      { id: "heading", position: { mobile: { x: 12, y: 24 } } },
      { id: "button", position: { mobile: { x: 12, y: 640 } } },
    ];

    expect(getRuntimeDirectElements(elements, "mobile")).toBe(elements);
    expect(getRuntimeDirectElements(elements, "desktop")).toBe(elements);
  });

  it("uses deliberate mobile/tablet/desktop crossover widths", () => {
    expect(getRuntimeViewportForWidth(320)).toBe("mobile");
    expect(getRuntimeViewportForWidth(390)).toBe("mobile");
    expect(getRuntimeViewportForWidth(412)).toBe("mobile");
    expect(getRuntimeViewportForWidth(430)).toBe("mobile");
    expect(getRuntimeViewportForWidth(480)).toBe("mobile");
    expect(getRuntimeViewportForWidth(600)).toBe("mobile");
    expect(getRuntimeViewportForWidth(601)).toBe("tablet");
    expect(getRuntimeViewportForWidth(768)).toBe("tablet");
    expect(getRuntimeViewportForWidth(769)).toBe("tablet");
    expect(getRuntimeViewportForWidth(1024)).toBe("tablet");
    expect(getRuntimeViewportForWidth(1025)).toBe("desktop");
  });

  it("accepts only internal protected-page return paths", () => {
    expect(getSafeProtectedReturnPath("?returnTo=%2Fmembers%2F")).toBe("/members");
    expect(getSafeProtectedReturnPath("?returnTo=%2F%2Fevil.example")).toBe("");
    expect(getSafeProtectedReturnPath("?returnTo=https%3A%2F%2Fevil.example")).toBe("");
  });
  it("keeps block collections scoped to the selected page", () => {
    const home = { id: "home", sections: [{ freeElements: [{ id: "heading", type: "heading" }] }] };
    const form = { id: "form", sections: [{ freeElements: [{ id: "form-block", type: "formBlock", connectedFormId: "form-1" }] }] };
    const buttons = { id: "buttons", sections: [{ freeElements: [{ id: "button", type: "button" }] }] };

    expect(getRuntimePageSections(home)[0].freeElements.map((item) => item.type)).toEqual(["heading"]);
    expect(getRuntimePageSections(form)[0].freeElements.map((item) => item.type)).toEqual(["formBlock"]);
    expect(getRuntimePageSections(buttons)[0].freeElements.map((item) => item.type)).toEqual(["button"]);
  });

  it("does not fall back to another page's blocks when the selected page is empty", () => {
    expect(getRuntimePageSections({ id: "empty", sections: [] })).toEqual([]);
    expect(getRuntimePageSections(null)).toEqual([]);
  });

  it("treats a login success destination as protected", () => {
    const flow = getRuntimeAuthFlow([loginPage, formPage]);

    expect(flow.entryPage).toBe(loginPage);
    expect(runtimePageRequiresAuthentication(formPage, flow.destinationPageIds)).toBe(true);
  });

  it("redirects a logged-out direct visit back to the login page", () => {
    const flow = getRuntimeAuthFlow([loginPage, formPage]);
    const resolved = resolveRuntimePage({
      pages: [loginPage, formPage],
      requestedPage: formPage,
      authEntryPage: flow.entryPage,
      authDestinationPageIds: flow.destinationPageIds,
      user: null,
      authLoading: false,
    });

    expect(resolved).toBe(loginPage);
  });

  it("allows the configured destination after login", () => {
    const flow = getRuntimeAuthFlow([loginPage, formPage]);
    const resolved = resolveRuntimePage({
      pages: [loginPage, formPage],
      requestedPage: formPage,
      authEntryPage: flow.entryPage,
      authDestinationPageIds: flow.destinationPageIds,
      user: { id: 2 },
      authLoading: false,
    });

    expect(resolved).toBe(formPage);
  });

  it("does not fall back to another page for an unknown public route", () => {
    expect(resolveRuntimePage({
      pages: [loginPage, formPage],
      allowDefaultFallback: false,
    })).toBeNull();
  });

  it("keeps hidden pages routable but out of header navigation", () => {
    const hiddenPage = { ...formPage, showInNavigation: false };
    expect(getRuntimeNavigationPages([loginPage, hiddenPage])).toEqual([loginPage]);
    expect(resolveRuntimePage({
      pages: [loginPage, hiddenPage],
      requestedPage: hiddenPage,
      user: { id: 2 },
    })).toBe(hiddenPage);
  });
});
