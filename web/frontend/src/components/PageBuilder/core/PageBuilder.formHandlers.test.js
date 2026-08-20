import { describe, expect, it, vi } from "vitest";
import { createFormHandlers } from "./PageBuilder.formHandlers";

describe("form page insertion", () => {
  it("creating a form does not add a form block to any page", () => {
    const project = { forms: [], workflows: [], pages: [{ id: "home", sections: [] }] };
    let updatedProject = project;
    const handlers = createFormHandlers({
      project,
      activeForm: null,
      updateProject: (updater) => { updatedProject = updater(updatedProject); },
      updateActiveForm: vi.fn(),
      setSelected: vi.fn(),
      createId: vi.fn(),
      createField: () => ({ id: "field-1" }),
      createForm: () => ({ id: "form-1", title: "Form 1" }),
      createWorkflow: () => ({ id: "workflow-1", formId: "form-1" }),
      getFormSections: () => [],
      getFormFields: () => [],
      getQuizSettings: () => ({}),
      cloneWithNewIds: (value) => value,
    });

    handlers.addForm();

    expect(updatedProject.forms).toHaveLength(1);
    expect(updatedProject.pages).toEqual(project.pages);
  });

  it("deleting a referenced form explicitly disconnects blocks without reassignment", () => {
    const form = { id: "form-1" };
    const project = {
      forms: [form, { id: "form-2" }],
      workflows: [{ id: "workflow-1", formId: "form-1" }],
      pages: [{ id: "home", sections: [{
        rows: [{ columns: [{ elements: [{
          id: "block-1", type: "formBlock", connectedFormId: "form-1",
        }] }] }],
        freeElements: [],
      }] }],
    };
    let updatedProject = project;
    const handlers = createFormHandlers({
      project,
      activeForm: form,
      updateProject: (updater) => { updatedProject = updater(updatedProject); },
      updateActiveForm: vi.fn(),
      setSelected: vi.fn(),
      createId: vi.fn(), createField: vi.fn(), createForm: vi.fn(), createWorkflow: vi.fn(),
      getFormSections: () => [], getFormFields: () => [], getQuizSettings: () => ({}),
      cloneWithNewIds: (value) => value,
    });

    handlers.deleteActiveForm();

    const block = updatedProject.pages[0].sections[0].rows[0].columns[0].elements[0];
    expect(block.connectedFormId).toBe("");
    expect(updatedProject.forms.map((item) => item.id)).toEqual(["form-2"]);
  });

  it("inserts a blank page after the selected page without changing existing work", () => {
    const originalSections = [
      {
        id: "page_1",
        title: "Buyer details",
        description: "Keep this description",
        fields: [{ id: "buyer", label: "Buyer name", type: "shortText", required: true }],
      },
      {
        id: "page_2",
        title: "Order details",
        description: "Keep this too",
        fields: [{ id: "currency", label: "Currency", type: "radio", options: ["EUR", "USD"] }],
      },
    ];
    const form = { id: "form_1", pageMode: "paged", sections: originalSections };
    let updatedForm = form;
    const updateActiveForm = vi.fn((updater) => {
      updatedForm = updater(updatedForm);
    });
    const handlers = createFormHandlers({
      project: { forms: [form], workflows: [] },
      activeForm: form,
      updateProject: vi.fn(),
      updateActiveForm,
      setSelected: vi.fn(),
      createId: () => "new_page",
      createField: vi.fn(),
      createForm: vi.fn(),
      createWorkflow: vi.fn(),
      getFormSections: (value) => value.sections,
      getFormFields: () => [],
      getQuizSettings: () => ({}),
      cloneWithNewIds: (value) => value,
    });

    handlers.addFormSection("page_1");

    expect(updatedForm.sections.map((section) => section.id)).toEqual([
      "page_1",
      "new_page",
      "page_2",
    ]);
    expect(updatedForm.sections[0]).toEqual(originalSections[0]);
    expect(updatedForm.sections[2]).toEqual(originalSections[1]);
    expect(updatedForm.sections[1]).toMatchObject({
      title: "Page 3",
      description: "",
      fields: [],
    });
  });
});
