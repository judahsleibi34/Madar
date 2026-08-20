import { describe, expect, it } from "vitest";

import { createPage } from "./PageBuilder.factories";
import {
  findPageByNavigationReference,
  getNavigablePages,
  getPageNavigationLabel,
} from "./PageBuilder.navigation";

describe("canonical builder page navigation", () => {
  const pages = [
    { id: "home", name: "Home", slug: "/", isDefault: true, showInNavigation: true },
    { id: "about", name: "About", slug: "/about" },
    { id: "hidden", name: "Hidden", slug: "/hidden", showInNavigation: false },
  ];

  it("keeps stable page order and treats missing visibility as visible", () => {
    expect(getNavigablePages(pages).map((page) => page.id)).toEqual(["home", "about"]);
  });

  it("uses a custom label without coupling it to page renames", () => {
    expect(getPageNavigationLabel({ name: "Renamed", navigationLabel: "Custom" })).toBe("Custom");
    expect(getPageNavigationLabel({ name: "Renamed" })).toBe("Renamed");
  });

  it("filters duplicate ids and routes safely", () => {
    expect(getNavigablePages([
      ...pages,
      { id: "about", name: "Duplicate ID", slug: "/other" },
      { id: "duplicate-route", name: "Duplicate route", slug: "/about" },
    ]).map((page) => page.id)).toEqual(["home", "about"]);
  });

  it("resolves CTA references and can omit the duplicate page link", () => {
    const contact = { id: "contact", name: "Contact", slug: "/contact" };
    const allPages = [...pages, contact];
    expect(findPageByNavigationReference(allPages, "Contact")).toBe(contact);
    expect(getNavigablePages(allPages, { excludePageIds: [contact.id] }))
      .not.toContain(contact);
  });

  it("creates normal public pages as visible navigation entries", () => {
    expect(createPage("Page 2").showInNavigation).toBe(true);
  });
});
