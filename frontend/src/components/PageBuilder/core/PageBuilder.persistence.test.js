import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createBuilderProjectPayload,
  persistBuilderProject,
  validateBuilderSaveAcknowledgement,
  validateBuilderSchemaAcknowledgement,
} from "./PageBuilder.persistence";
import {
  cleanBuilderProject,
  buildFormConnectionUpdate,
  repairDuplicateProjectIds,
} from "./PageBuilder.project";
import { loadInitialProject } from "./PageBuilder.storage";
import { collectFormConnectionIssues } from "./PageBuilder.errors";
import { stripEditorOnlyState } from "./PageBuilder.editorState";
import { getSectionElements } from "./PageBuilder.layout";

const fullProject = {
  id: "project_regression",
  name: "Saved forms",
  slug: "saved-forms",
  activeFormId: "form_1",
  forms: [{
    id: "form_1",
    title: "Nine-page form",
    pageMode: "paged",
    sections: Array.from({ length: 9 }, (_, pageIndex) => ({
      id: `page_${pageIndex + 1}`,
      title: `Page ${pageIndex + 1}`,
      fields: [{
        id: `field_${pageIndex + 1}`,
        label: `Question ${pageIndex + 1}`,
        type: "shortText",
        required: pageIndex % 2 === 0,
      }],
    })),
  }],
};

describe("builder project persistence", () => {
  beforeEach(() => localStorage.clear());

  it("writes the complete multi-page form to the browser draft", () => {
    const setProject = vi.fn();

    persistBuilderProject({
      nextProject: fullProject,
      storageKey: "builder-regression",
      setProject,
      showToast: vi.fn(),
      demoMode: false,
    });

    expect(JSON.parse(localStorage.getItem("builder-regression"))).toEqual(
      stripEditorOnlyState(fullProject)
    );
    expect(setProject).toHaveBeenCalledWith(fullProject);
  });

  it("keeps the full form tree in the backend draft_schema payload", () => {
    const payload = createBuilderProjectPayload({
      project: fullProject,
      builderProjectRecord: { slug: "saved-forms" },
      getBuilderProjectName: (project) => project.name,
      getBuilderProjectSlug: (project) => project.slug,
    });

    expect(payload.draft_schema).toEqual(stripEditorOnlyState(fullProject));
    expect(payload.draft_schema).not.toBe(fullProject);
    expect(payload.draft_schema.forms[0].sections).toHaveLength(9);
    expect(payload.draft_schema.forms[0].sections[8].fields[0].label).toBe("Question 9");
  });

  it("preserves explicit button colors in browser and backend draft payloads", () => {
    const project = {
      ...fullProject,
      pages: [{
        id: "home",
        sections: [{ freeElements: [{
          id: "button-1",
          type: "button",
          backgroundColor: "#112233",
          textColor: "#FFFFFF",
          hoverBackgroundColor: "#334455",
          hoverTextColor: "#EEEEEE",
          borderColor: "#556677",
        }] }],
      }],
    };
    persistBuilderProject({
      nextProject: project,
      storageKey: "button-color-draft",
      setProject: vi.fn(),
      showToast: vi.fn(),
      demoMode: false,
    });
    const localButton = JSON.parse(localStorage.getItem("button-color-draft"))
      .pages[0].sections[0].freeElements[0];
    const payloadButton = createBuilderProjectPayload({
      project,
      builderProjectRecord: { id: "project-1", slug: "buttons" },
      getBuilderProjectName: () => "Buttons",
      getBuilderProjectSlug: () => "buttons",
    }).draft_schema.pages[0].sections[0].freeElements[0];
    expect(localButton).toMatchObject(payloadButton);
    expect(payloadButton).toMatchObject({
      backgroundColor: "#112233",
      textColor: "#FFFFFF",
      hoverBackgroundColor: "#334455",
      hoverTextColor: "#EEEEEE",
      borderColor: "#556677",
    });
  });

  it("sends the backend revision when updating an existing project", () => {
    const payload = createBuilderProjectPayload({
      project: fullProject,
      builderProjectRecord: { id: "project-1", draft_revision: 12 },
      getBuilderProjectName: (project) => project.name,
      getBuilderProjectSlug: (project) => project.slug,
    });

    expect(payload).toMatchObject({ expected_revision: 12 });
  });

  it("requires an acknowledgement for the exact project with a newer revision", () => {
    expect(validateBuilderSaveAcknowledgement({
      projectId: "project-1",
      previousRevision: 5,
      savedRecord: { id: "project-1", draft_revision: 6 },
    })).toBe(6);
    expect(() => validateBuilderSaveAcknowledgement({
      projectId: "project-1",
      previousRevision: 5,
      savedRecord: { id: "project-2", draft_revision: 6 },
    })).toThrow(/acknowledgement/i);
    expect(() => validateBuilderSaveAcknowledgement({
      projectId: "project-1",
      previousRevision: 5,
      savedRecord: { id: "project-1", draft_revision: 5 },
    })).toThrow(/acknowledgement/i);
  });

  it("accepts reordered acknowledgement objects but rejects real schema differences", () => {
    const submittedProject = {
      pages: [{ id: "home", settings: { title: "Home", visible: true } }],
      theme: { colors: { surface: "#fff", primary: "#111" } },
    };
    const reorderedSchema = {
      theme: { colors: { primary: "#111", surface: "#fff" } },
      pages: [{ settings: { visible: true, title: "Home" }, id: "home" }],
    };

    expect(validateBuilderSchemaAcknowledgement({
      savedRecord: { draft_schema: reorderedSchema },
      submittedProject,
    })).toBe(true);
    expect(() => validateBuilderSchemaAcknowledgement({
      savedRecord: {
        draft_schema: {
          ...reorderedSchema,
          pages: [{ settings: { visible: true, title: "Changed" }, id: "home" }],
        },
      },
      submittedProject,
    })).toThrow(/does not match/);
  });

  it("excludes all editor selections while retaining public routing state", () => {
    const payload = createBuilderProjectPayload({
      project: {
        ...fullProject,
        activePageId: "page-2",
        activeWorkflowId: "workflow-1",
        activeRoleId: "role-1",
        defaultPageId: "home",
        pages: [{ id: "home", isDefault: true }, { id: "page-2" }],
      },
      builderProjectRecord: { id: "project-1", draft_revision: 12 },
      getBuilderProjectName: (project) => project.name,
      getBuilderProjectSlug: (project) => project.slug,
    });

    expect(payload.draft_schema).not.toHaveProperty("activePageId");
    expect(payload.draft_schema).not.toHaveProperty("activeFormId");
    expect(payload.draft_schema).not.toHaveProperty("activeWorkflowId");
    expect(payload.draft_schema).not.toHaveProperty("activeRoleId");
    expect(payload.draft_schema.defaultPageId).toBe("home");
    expect(payload.draft_schema.pages[0].isDefault).toBe(true);
  });

  it("keeps compatibility with records created before revision support", () => {
    const payload = createBuilderProjectPayload({
      project: fullProject,
      builderProjectRecord: { id: "project-1" },
      getBuilderProjectName: (project) => project.name,
      getBuilderProjectSlug: (project) => project.slug,
    });

    expect(payload).not.toHaveProperty("expected_revision");
  });

  it("does not truncate the saved form when overwriting a previous draft", () => {
    localStorage.setItem("builder-regression", JSON.stringify({ name: "Old draft", forms: [] }));

    persistBuilderProject({
      nextProject: fullProject,
      storageKey: "builder-regression",
      setProject: vi.fn(),
      showToast: vi.fn(),
      demoMode: false,
    });

    expect(JSON.parse(localStorage.getItem("builder-regression"))).toEqual(
      stripEditorOnlyState(fullProject)
    );
    expect(JSON.parse(localStorage.getItem("builder-regression:backup"))).toEqual({
      name: "Old draft",
      forms: [],
    });
  });

  it("round-trips a connected form from editor update through publish payload", () => {
    const storageKey = "form-connection-roundtrip";
    const block = { id: "block-1", type: "formBlock", connectedFormId: "" };
    const editorProject = {
      id: "project-1",
      name: "Connected form project",
      slug: "connected-form-project",
      forms: [{ id: "form-1", title: "Form 1", sections: [] }],
      activeFormId: "form-1",
      pages: [{
        id: "home",
        name: "Home",
        slug: "/",
        sections: [{ rows: [{ columns: [{ elements: [block] }] }] }],
      }],
      activePageId: "home",
    };
    Object.assign(block, buildFormConnectionUpdate("form-1"));
    const normalized = cleanBuilderProject(editorProject);

    persistBuilderProject({
      nextProject: normalized,
      storageKey,
      setProject: vi.fn(),
      showToast: vi.fn(),
      demoMode: false,
    });
    const reloaded = loadInitialProject(storageKey);
    const payload = createBuilderProjectPayload({
      project: reloaded,
      builderProjectRecord: { id: "project-1", draft_revision: 4 },
      getBuilderProjectName: (project) => project.name,
      getBuilderProjectSlug: (project) => project.slug,
    });
    const reloadedBlock = payload.draft_schema.pages[0].sections
      .flatMap(getSectionElements)
      .find((element) => element.id === "block-1");

    expect(reloadedBlock.connectedFormId).toBe("form-1");
    expect(collectFormConnectionIssues(payload.draft_schema)).toEqual([]);
  });

  it("persists repaired ids across save and reload without changing form connections", () => {
    const storageKey = "duplicate-id-roundtrip";
    const corrupted = {
      id: "project-1",
      name: "Repair roundtrip",
      slug: "repair-roundtrip",
      pages: [
        { id: "home", name: "Home", sections: [{ mode: "direct", freeElements: [
          { id: "duplicate", type: "text", content: "Keep" },
        ] }] },
        { id: "page-2", name: "Page 2", sections: [{ mode: "direct", freeElements: [
          { id: "duplicate", type: "formBlock", connectedFormId: "form-1" },
        ] }] },
      ],
      forms: [{ id: "form-1", title: "Form 1", sections: [] }],
    };
    const repaired = repairDuplicateProjectIds(corrupted, {
      idFactory: () => "element_repaired",
    }).project;

    persistBuilderProject({
      nextProject: repaired,
      storageKey,
      setProject: vi.fn(),
      showToast: vi.fn(),
      demoMode: false,
    });
    const reloaded = loadInitialProject(storageKey);
    const blocks = reloaded.pages.flatMap((page) =>
      page.sections.flatMap((section) => section.freeElements || [])
    );

    expect(blocks.map((block) => block.id)).toEqual(["duplicate", "element_repaired"]);
    expect(blocks[1].connectedFormId).toBe("form-1");
    expect(new Set(blocks.map((block) => block.id)).size).toBe(blocks.length);
  });
});
