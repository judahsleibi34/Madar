import { describe, expect, it } from "vitest";

import { resolveInspectorMode, resolveInspectorPage } from "./PageBuilder.inspector";

const project = {
  activePageId: "missing",
  defaultPageId: "home",
  pages: [{ id: "home", name: "Home" }, { id: "page-2", name: "Page 2" }],
};

describe("page builder inspector context", () => {
  it("falls back from an invalid local selection to the persisted default page", () => {
    expect(resolveInspectorPage(project)?.id).toBe("home");
  });

  it("updates immediately when the active page is valid", () => {
    expect(resolveInspectorPage({ ...project, activePageId: "page-2" })?.name).toBe("Page 2");
  });

  it("prioritizes valid elements and sections, then falls back to the page", () => {
    const activePage = project.pages[0];
    expect(resolveInspectorMode({
      selected: { type: "element" }, selectedElement: { id: "block" }, activePage,
    })).toBe("element");
    expect(resolveInspectorMode({
      selected: { type: "section" }, selectedSection: { id: "section" }, activePage,
    })).toBe("section");
    expect(resolveInspectorMode({
      selected: { type: "element", id: "deleted" }, selectedElement: null, activePage,
    })).toBe("page");
  });
});
