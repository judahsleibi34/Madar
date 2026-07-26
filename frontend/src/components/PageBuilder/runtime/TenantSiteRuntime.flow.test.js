import { describe, expect, it } from "vitest";
import {
  getRuntimeAuthFlow,
  getRuntimeCanvasScale,
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

describe("tenant runtime page flow", () => {
  it("scales a logical canvas down to the available browser width", () => {
    expect(getRuntimeCanvasScale(1000, 1200)).toBeCloseTo(5 / 6);
    expect(getRuntimeCanvasScale(390, 390)).toBe(1);
    expect(getRuntimeCanvasScale(1600, 1200)).toBe(1);
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
