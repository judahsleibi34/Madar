import { describe, expect, it } from "vitest";

import {
  getBuilderProjectIdFromPath,
  getBuilderWorkspaceFromPath,
  getBuilderWorkspacePath,
} from "./PageBuilder.workspaceRouting";

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
});
