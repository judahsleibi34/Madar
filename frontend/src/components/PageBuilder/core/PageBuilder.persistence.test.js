import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  createBuilderProjectPayload,
  persistBuilderProject,
} from "./PageBuilder.persistence";

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
});
