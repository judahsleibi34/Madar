import { describe, expect, it, vi } from "vitest";
import { createFormHandlers } from "./PageBuilder.formHandlers";

describe("form page insertion", () => {
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
