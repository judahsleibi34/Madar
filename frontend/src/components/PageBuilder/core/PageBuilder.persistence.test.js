import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createBuilderProjectPayload,
  persistBuilderProject,
} from "./PageBuilder.persistence";
import {
  cleanBuilderProject,
  buildFormConnectionUpdate,
  repairDuplicateProjectIds,
} from "./PageBuilder.project";
import { loadInitialProject } from "./PageBuilder.storage";
import { collectFormConnectionIssues } from "./PageBuilder.errors";

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

    expect(JSON.parse(localStorage.getItem("builder-regression"))).toEqual(fullProject);
    expect(setProject).toHaveBeenCalledWith(fullProject);
  });

  it("keeps the full form tree in the backend draft_schema payload", () => {
    const payload = createBuilderProjectPayload({
      project: fullProject,
      builderProjectRecord: { slug: "saved-forms" },
      getBuilderProjectName: (project) => project.name,
      getBuilderProjectSlug: (project) => project.slug,
    });

    expect(payload.draft_schema).toBe(fullProject);
    expect(payload.draft_schema.forms[0].sections).toHaveLength(9);
    expect(payload.draft_schema.forms[0].sections[8].fields[0].label).toBe("Question 9");
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

    expect(JSON.parse(localStorage.getItem("builder-regression"))).toEqual(fullProject);
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
      .flatMap((section) => section.freeElements || [])
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
