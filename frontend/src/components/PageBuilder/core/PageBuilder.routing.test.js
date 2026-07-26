import { describe, expect, it } from "vitest";

import {
  collectPublicPageRoutingIssues,
  createNextGeneratedPageName,
  createUniqueBuilderPageName,
  createUniquePublicPageSlug,
  getDefaultPublicPage,
  getProductionFormUrl,
  getProductionTenantUrl,
  getStandaloneFormPath,
  getPublicPagePath,
  normalizePublicPageSlug,
  normalizeProjectPageRouting,
  resolvePublicPageByPath,
  setProjectDefaultPage,
} from "./PageBuilder.routing";

const multiPageProject = {
  activePageId: "form",
  pages: [
    { id: "home", name: "Home", slug: "/", showInNavigation: true, sections: [{ freeElements: [{ id: "hero", type: "heading" }] }] },
    { id: "form", name: "Form", slug: "/form", showInNavigation: true, sections: [{ freeElements: [{ id: "form-block", type: "formBlock", connectedFormId: "form-1" }] }] },
    { id: "about", name: "About", slug: "/about", showInNavigation: false, sections: [] },
  ],
  forms: [{ id: "form-1" }],
};

describe("public page routing contract", () => {
  it("generates a safe unique address from a non-technical page name", () => {
    const pages = [
      { id: "home", name: "Home", slug: "/" },
      { id: "services", name: "Services", slug: "/our-services" },
    ];

    expect(createUniquePublicPageSlug({
      name: "Our Services",
      pages,
      currentPageId: "new-page",
    })).toBe("/our-services-2");
    expect(createUniquePublicPageSlug({
      name: "Login",
      pages,
      currentPageId: "new-page",
    })).toBe("/login-page");
    expect(createUniquePublicPageSlug({
      name: "Anything",
      pages,
      currentPageId: "home",
      isDefault: true,
    })).toBe("/");
  });

  it("generates unique page names after deletion and repairs existing duplicates", () => {
    const pages = [
      { id: "home", name: "Home", slug: "/" },
      { id: "page-3", name: "Page 3", slug: "/page-3" },
    ];
    expect(createNextGeneratedPageName(pages)).toBe("Page 4");
    expect(createUniqueBuilderPageName({ name: "Page 3", pages })).toBe("Page 4");

    const normalized = normalizeProjectPageRouting({
      pages: [...pages, { id: "duplicate", name: "Page 3", slug: "/page-3-2" }],
    });
    expect(normalized.pages.map((page) => page.name)).toEqual(["Home", "Page 3", "Page 4"]);
    expect(normalized.pages.map((page) => page.slug)).toEqual(["/", "/page-3", "/page-3-2"]);
  });

  it("preserves trailing whitespace while a page name is being typed", () => {
    expect(createUniqueBuilderPageName({
      name: "Home ",
      pages: [{ id: "home", name: "Home" }],
      currentPageId: "home",
      preserveOuterWhitespace: true,
    })).toBe("Home ");
  });

  it("keeps Home as root regardless of the editor-selected page", () => {
    const project = normalizeProjectPageRouting(multiPageProject);

    expect(project.defaultPageId).toBe("home");
    expect(project.pages[0]).toMatchObject({ id: "home", slug: "/", isDefault: true, order: 0 });
    expect(getDefaultPublicPage(project.pages, project.defaultPageId)?.id).toBe("home");
    expect(resolvePublicPageByPath(project.pages, "/", project.defaultPageId)?.id).toBe("home");
    expect(resolvePublicPageByPath(project.pages, "/form", project.defaultPageId)?.id).toBe("form");
    expect(resolvePublicPageByPath(project.pages, "/about", project.defaultPageId)?.id).toBe("about");
    expect(resolvePublicPageByPath(project.pages, "/missing", project.defaultPageId)).toBeNull();
  });

  it("preserves and resolves nested public page slugs", () => {
    const pages = [{ id: "team", name: "Team", slug: "/about/team" }];
    expect(normalizePublicPageSlug("/about/team", "Team")).toBe("/about/team");
    expect(resolvePublicPageByPath(pages, "/about/team")?.id).toBe("team");
    expect(getPublicPagePath("/site/acme", pages[0])).toBe("/site/acme/about/team");
  });

  it("builds canonical root and direct-page URLs", () => {
    const project = normalizeProjectPageRouting(multiPageProject);
    expect(getPublicPagePath("/site/madar", project.pages[0])).toBe("/site/madar/");
    expect(getPublicPagePath("/site/madar", project.pages[1])).toBe("/site/madar/form");
  });

  it("builds production tenant URLs on the deployed path-based host", () => {
    expect(
      getProductionTenantUrl(
        { publish: { subdomain: "disco2", siteBaseDomain: "madar.app" } },
        "/forms/form-1"
      )
    ).toBe("https://madarportal.com/site/disco2/forms/form-1");
  });

  it("builds a standalone respondent form link outside the website route", () => {
    const project = { publish: { subdomain: "disco2" } };

    expect(getStandaloneFormPath(project, "form-1")).toBe(
      "/forms/disco2/form-1"
    );
    expect(getProductionFormUrl(project, "form-1")).toBe(
      "https://madarportal.com/forms/disco2/form-1"
    );
  });

  it("repairs missing and duplicate slugs deterministically without reordering pages", () => {
    const project = normalizeProjectPageRouting({
      pages: [
        { id: "home", name: "Home", slug: "/" },
        { id: "one", name: "Services", slug: "/services" },
        { id: "two", name: "Services copy", slug: "/services" },
        { id: "three", name: "Contact", slug: "" },
      ],
    });

    expect(project.pages.map((page) => page.id)).toEqual(["home", "one", "two", "three"]);
    expect(project.pages.map((page) => page.slug)).toEqual(["/", "/services", "/services-2", "/contact"]);
    expect(normalizeProjectPageRouting(project)).toEqual(project);
  });

  it("sets exactly one new homepage and safely promotes a page after deletion", () => {
    const changed = setProjectDefaultPage(normalizeProjectPageRouting(multiPageProject), "form");
    expect(changed.defaultPageId).toBe("form");
    expect(changed.pages.filter((page) => page.isDefault)).toHaveLength(1);
    expect(changed.pages.find((page) => page.id === "form")?.slug).toBe("/");
    expect(changed.pages.find((page) => page.id === "home")?.slug).toBe("/home");

    const afterDelete = normalizeProjectPageRouting({
      ...changed,
      defaultPageId: "",
      pages: changed.pages.filter((page) => page.id !== "form"),
    });
    expect(afterDelete.defaultPageId).toBe("home");
    expect(afterDelete.pages[0].isDefault).toBe(true);
  });

  it("reports reserved public page links", () => {
    const project = normalizeProjectPageRouting({
      pages: [
        { id: "home", name: "Home", slug: "/" },
        { id: "login", name: "Login", slug: "/login" },
      ],
    });
    expect(collectPublicPageRoutingIssues(project)).toEqual([
      expect.objectContaining({ issue_type: "reserved_page_slug", page_id: "login" }),
    ]);
  });
});
