import { describe, expect, it } from "vitest";

import {
  builderTabPathById,
  builderDesignPanelPathById,
  getBuilderTabFromPath,
  getBuilderDesignPanelFromPath,
  getBuilderProjectIdFromPath,
  getBuilderWorkspaceFromPath,
  getBuilderWorkspacePath,
} from "./PageBuilder.workspaceRouting";

describe("editor route compatibility", () => {
  it.each([
    ["design", "pages"], ["forms", "forms"], ["reservations", "reservations"],
    ["chrome", "header-footer"], ["users", "users"], ["theme", "website-theme"],
    ["publish", "publish"], ["data", "data"], ["responses", "responses"],
    ["workflows", "workflows"],
  ])("preserves legacy and project paths for %s", (tab, segment) => {
    expect(builderTabPathById[tab]).toBe(`/page-builder/${segment}`);
    expect(getBuilderWorkspacePath("a", tab)).toBe(`/page-builder/projects/a/${segment}`);
  });

  it.each([
    ["pages", "design"], ["design", "design"], ["forms", "forms"],
    ["reservations", "reservations"], ["chrome", "chrome"], ["header", "chrome"],
    ["footer", "chrome"], ["header-footer", "chrome"], ["users", "users"],
    ["theme", "design"], ["themes", "design"], ["website-theme", "design"],
    ["site-theme", "design"], ["publish", "publish"], ["data", "data"],
    ["responses", "responses"], ["workflows", "workflows"],
  ])("preserves reverse alias %s", (segment, tab) => {
    for (const prefix of ["/page-builder", "/page-builder/projects/a", "/e-learning/landing-page", "/e-learning/landing-page/projects/a"]) {
      for (const suffix of ["", "/", "?preview=1", "#anchor"]) {
        expect(getBuilderTabFromPath(`${prefix}/${segment}${suffix}`)).toBe(tab);
      }
    }
  });

  it.each(["theme", "themes", "website-theme", "site-theme", "pages/themes", "design/themes"])("preserves theme panel interpretation for %s", segment => {
    for (const suffix of ["", "/", "?preview=1", "#anchor"]) {
      expect(getBuilderDesignPanelFromPath(`/page-builder/${segment}${suffix}`)).toBe("Themes");
      expect(getBuilderDesignPanelFromPath(`/page-builder/projects/a/${segment}${suffix}`)).toBe("Themes");
      expect(getBuilderDesignPanelFromPath(`/e-learning/landing-page/projects/a/${segment}${suffix}`)).toBe("Themes");
      expect(getBuilderDesignPanelFromPath(`/e-learning/landing-page/${segment}${suffix}`)).toBe("Pages");
    }
  });

  it.each(["pages", "design"])("preserves section panels under %s", segment => {
    expect(getBuilderDesignPanelFromPath(`/page-builder/${segment}/sections/`)).toBe("Sections");
    expect(getBuilderDesignPanelFromPath(`/e-learning/landing-page/projects/a/${segment}/sections?x=1`)).toBe("Sections");
    expect(getBuilderDesignPanelFromPath(`/e-learning/landing-page/${segment}/sections`)).toBe("Pages");
  });

  it.each(["", "/", "/other/pages", "/page-builder", "/page-builder/unknown", "/data-sources/projects/a/data", "/business-intelligence/projects/a/data", "/builder-responses/projects/a/responses"])("preserves unrelated or unknown path %s", path => {
    expect(getBuilderTabFromPath(path)).toBeNull();
    expect(getBuilderDesignPanelFromPath(path)).toBe("Pages");
  });

  it("retains distinct unknown-tab fallbacks and panel paths", () => {
    expect(builderTabPathById.unknown).toBeUndefined();
    expect(getBuilderWorkspacePath("a", "unknown")).toBe("/page-builder/projects/a/pages");
    expect(builderDesignPanelPathById).toEqual({ Pages: "/page-builder/pages", Sections: "/page-builder/pages/sections", Themes: "/page-builder/pages/themes" });
    expect(builderDesignPanelPathById.unknown).toBeUndefined();
    expect(getBuilderDesignPanelFromPath("/page-builder/pages/unknown")).toBe("Pages");
    expect(getBuilderDesignPanelFromPath("/page-builder/themes-extra")).toBe("Pages");
    expect(getBuilderDesignPanelFromPath("/page-builder/pages?panel=/themes")).toBe("Pages");
  });

  it("preserves encoded identities without changing malformed-input behavior", () => {
    const path = getBuilderWorkspacePath("a/b عربي?#", "design");
    expect(path).toBe(`/page-builder/projects/${encodeURIComponent("a/b عربي?#")}/pages`);
    expect(getBuilderProjectIdFromPath(path)).toBe("a/b عربي?#");
    expect(getBuilderTabFromPath(path)).toBe("design");
    expect(() => getBuilderProjectIdFromPath("/page-builder/projects/%ZZ/pages")).toThrow(URIError);
    expect(getBuilderTabFromPath("/page-builder/projects/%ZZ/pages")).toBe("design");
    expect(getBuilderTabFromPath()).toBeNull();
    expect(() => getBuilderTabFromPath(null)).toThrow(TypeError);
    expect(getBuilderDesignPanelFromPath(null)).toBe("Pages");
  });
});

describe("explicit builder project routes", () => {
  it("builds refresh-safe routes for each backend project", () => {
    expect(getBuilderWorkspacePath("project-a", "design"))
      .toBe("/page-builder/projects/project-a/pages");
    expect(getBuilderWorkspacePath("project-b", "responses", "builder-responses"))
      .toBe("/builder-responses/projects/project-b/responses");
  });

  it("extracts exact project identity and workspace from a route", () => {
    const path = "/page-builder/projects/9db8/pages/sections";
    expect(getBuilderProjectIdFromPath(path)).toBe("9db8");
    expect(getBuilderWorkspaceFromPath(path)).toBe("page-builder");
  });

  it("keeps projects distinct for switching and refresh", () => {
    expect(getBuilderWorkspacePath("project-a")).not.toBe(getBuilderWorkspacePath("project-b"));
    expect(getBuilderProjectIdFromPath("/page-builder/pages")).toBe("");
  });

  it("keeps Data Sources in its own project namespace", () => {
    const path = getBuilderWorkspacePath("source-project", "data", "data-sources");
    expect(path).toBe("/data-sources/projects/source-project/data");
    expect(getBuilderProjectIdFromPath(path)).toBe("source-project");
    expect(getBuilderWorkspaceFromPath(path)).toBe("data-sources");
  });

  it("keeps Business Intelligence in its own project namespace", () => {
    const path = getBuilderWorkspacePath("bi-project", "data", "business-intelligence");
    expect(path).toBe("/business-intelligence/projects/bi-project/data");
    expect(getBuilderProjectIdFromPath(path)).toBe("bi-project");
    expect(getBuilderWorkspaceFromPath(path)).toBe("business-intelligence");
  });

  it("keeps Academy workspaces in the dedicated E-Learning namespace", () => {
    const workspace = "e-learning/landing-page";
    const path = getBuilderWorkspacePath("academy-owner", "publish", workspace);
    expect(path).toBe("/e-learning/landing-page/projects/academy-owner/publish");
    expect(getBuilderProjectIdFromPath(path)).toBe("academy-owner");
    expect(getBuilderWorkspaceFromPath(path)).toBe(workspace);
    expect(getBuilderWorkspacePath("academy-owner", "chrome", workspace)).toContain("/e-learning/landing-page/projects/academy-owner/header-footer");
  });
});
