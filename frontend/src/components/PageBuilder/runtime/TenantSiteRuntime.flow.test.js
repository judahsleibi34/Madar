import { describe, expect, it } from "vitest";
import {
  getRuntimeAuthFlow,
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

  it("falls back to the first page for an unknown route", () => {
    expect(resolveRuntimePage({ pages: [loginPage, formPage] })).toBe(loginPage);
  });
});
