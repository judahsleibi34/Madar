import { describe, expect, it } from "vitest";

import {
  EDITOR_ONLY_PROJECT_FIELDS,
  arePersistableProjectsEqual,
  getPersistableProject,
  getProjectEditorDefaults,
  serializePersistableProject,
  stripEditorOnlyState,
  stripDeviceLocalProjectState,
  withLocalProjectEditorDefaults,
} from "./PageBuilder.editorState";

describe("device-local builder state", () => {
  it("excludes server lifecycle metadata and volatile publish timestamps from identity", () => {
    const project = {
      status: "published",
      draft_revision: 8,
      published_revision: 3,
      published_version: 4,
      updated_at: "now",
      last_published_at: "then",
      pages: [{ id: "home" }],
      publish: { environment: "live", lastSavedAt: "one", lastPublishedAt: "two" },
    };
    const persisted = getPersistableProject(project);

    expect(persisted).toEqual({ pages: [{ id: "home" }], publish: { environment: "live" } });
    expect(arePersistableProjectsEqual(project, {
      pages: [{ id: "home" }],
      publish: { environment: "live" },
    })).toBe(true);
  });

  it("serializes persistable objects canonically", () => {
    expect(serializePersistableProject({ pages: [{ name: "Home", id: "home" }], name: "Site" }))
      .toBe(serializePersistableProject({ name: "Site", pages: [{ id: "home", name: "Home" }] }));
  });
  it("does not persist editor selection in the shared cloud schema", () => {
    const project = {
      name: "Shared",
      pages: [{ id: "home" }],
      forms: [{ id: "form-1" }],
      workflows: [{ id: "workflow-1" }],
      roles: [{ id: "role-1" }],
      activePageId: "home",
      activeFormId: "form-1",
      activeWorkflowId: "workflow-1",
      activeRoleId: "role-1",
    };
    const shared = stripDeviceLocalProjectState(project);
    expect(shared).toEqual({
      name: "Shared",
      pages: [{ id: "home" }],
      forms: [{ id: "form-1" }],
      workflows: [{ id: "workflow-1" }],
      roles: [{ id: "role-1" }],
    });
    expect(project.activePageId).toBe("home");
  });

  it("derives editor defaults locally from shared collections", () => {
    expect(getProjectEditorDefaults({
      pages: [{ id: "home" }],
      forms: [{ id: "form-1" }],
    })).toMatchObject({ activePageId: "home", activeFormId: "form-1" });
  });

  it("is immutable and idempotent while preserving unknown shared fields", () => {
    const project = {
      activePageId: "page-2",
      defaultPageId: "home",
      customSupportedField: { keep: true },
      pages: [{ id: "home" }, { id: "page-2" }],
    };
    const once = stripEditorOnlyState(project);
    const twice = stripEditorOnlyState(once);

    expect(once).toEqual(twice);
    expect(once.customSupportedField).toEqual({ keep: true });
    expect(once.defaultPageId).toBe("home");
    expect(project.activePageId).toBe("page-2");
  });

  it("excludes every declared editor-only selection", () => {
    const project = Object.fromEntries(
      EDITOR_ONLY_PROJECT_FIELDS.map((field) => [field, `${field}-value`])
    );
    expect(stripEditorOnlyState(project)).toEqual({});
  });

  it("ignores legacy cloud selections and chooses the persisted default page locally", () => {
    const hydrated = withLocalProjectEditorDefaults({
      activePageId: "page-2",
      defaultPageId: "home",
      pages: [{ id: "home" }, { id: "page-2" }],
      forms: [{ id: "form-1" }],
    });
    expect(hydrated.activePageId).toBe("home");
    expect(hydrated.activeFormId).toBe("form-1");
    expect(hydrated.defaultPageId).toBe("home");
  });
});
