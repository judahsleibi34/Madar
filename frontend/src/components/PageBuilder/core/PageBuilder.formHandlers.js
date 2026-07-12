export const createFormHandlers = ({
  project,
  activeForm,
  updateProject,
  updateActiveForm,
  setSelected,
  createId,
  createField,
  createForm,
  createWorkflow,
  getFormSections,
  getFormFields,
  getQuizSettings,
  cloneWithNewIds,
}) => {
  const addForm = () => {
    const form = createForm(`Form ${project.forms.length + 1}`, [
      createField("Question 1", "shortText"),
    ]);

    updateProject((prev) => ({
      ...prev,
      forms: [...prev.forms, form],
      activeFormId: form.id,
      workflows: [
        ...prev.workflows,
        createWorkflow(`After ${form.title} is submitted`, form.id),
      ],
    }));

    setSelected({ type: "form", id: form.id });
  };

  const deleteActiveForm = () => {
    if (!activeForm) return;

    const remainingForms = (project.forms || []).filter((form) => form.id !== activeForm.id);
    const nextForm = remainingForms[0] || null;

    updateProject((prev) => ({
      ...prev,
      forms: (prev.forms || []).filter((form) => form.id !== activeForm.id),
      activeFormId: nextForm?.id || "",
      workflows: (prev.workflows || []).filter((workflow) => workflow.formId !== activeForm.id),
      pages: (prev.pages || []).map((page) => ({
        ...page,
        sections: (page.sections || []).map((section) => ({
          ...section,
          rows: (section.rows || []).map((row) => ({
            ...row,
            columns: (row.columns || []).map((column) => ({
              ...column,
              elements: (column.elements || []).map((element) =>
                element.connectedFormId === activeForm.id
                  ? { ...element, connectedFormId: nextForm?.id || "" }
                  : element
              ),
            })),
          })),
          freeElements: (section.freeElements || []).map((element) =>
            element.connectedFormId === activeForm.id
              ? { ...element, connectedFormId: nextForm?.id || "" }
              : element
          ),
        })),
      })),
    }));

    setSelected({ type: "form", id: nextForm?.id || "" });
  };

  const addFormSection = (afterSectionId = null) => {
    updateActiveForm((form) => {
      const sections = getFormSections(form);
      const usedPageNumbers = sections
        .map((section, index) => {
          const match = String(section.title || "").match(/^Page\s+(\d+)$/i);
          return match ? Number(match[1]) : index + 1;
        })
        .filter((value) => Number.isFinite(value));
      const nextPageNumber = Math.max(1, ...usedPageNumbers) + 1;

      const newSection = {
        id: createId("formSection"),
        title: `Page ${nextPageNumber}`,
        description: "",
        collapsed: false,
        fields: [],
      };
      const insertionIndex = afterSectionId
        ? sections.findIndex((section) => section.id === afterSectionId) + 1
        : sections.length;
      const nextSections = [...sections];
      nextSections.splice(insertionIndex > 0 ? insertionIndex : sections.length, 0, newSection);

      return {
        ...form,
        pageMode: "paged",
        sections: nextSections,
      };
    });
  };

  const addFieldToForm = (sectionId = null, type = "shortText") => {
    if (!activeForm) return;

    const field = createField(`Question ${getFormFields(activeForm).length + 1}`, type);

    updateActiveForm((form) => {
      const sections = getFormSections(form);

      if (!sections.length || !sectionId) {
        return {
          ...form,
          fields: [...(form.fields || []), field],
        };
      }

      return {
        ...form,
        sections: sections.map((section) =>
          section.id === sectionId
            ? { ...section, fields: [...(section.fields || []), field] }
            : section
        ),
      };
    });
  };

  const updateActiveFormQuiz = (updates) => {
    updateActiveForm((form) => ({
      ...form,
      quiz: {
        ...getQuizSettings(form),
        ...updates,
      },
    }));
  };

  const updateFormField = (fieldId, updates) => {
    updateActiveForm((form) => ({
      ...form,
      fields: (form.fields || []).map((field) =>
        field.id === fieldId ? { ...field, ...updates } : field
      ),
      sections: getFormSections(form).map((section) => ({
        ...section,
        fields: (section.fields || []).map((field) =>
          field.id === fieldId ? { ...field, ...updates } : field
        ),
      })),
    }));
  };

  const updateFormSection = (sectionId, updates) => {
    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).map((section) =>
        section.id === sectionId ? { ...section, ...updates } : section
      ),
    }));
  };

  const moveFormField = (fieldId, direction) => {
    updateActiveForm((form) => {
      const sections = getFormSections(form);
      const sectionIndex = sections.findIndex((section) =>
        (section.fields || []).some((field) => field.id === fieldId)
      );

      if (sectionIndex === -1) {
        const fields = [...(form.fields || [])];
        const index = fields.findIndex((field) => field.id === fieldId);
        const targetIndex = direction === "up" ? index - 1 : index + 1;

        if (index < 0 || targetIndex < 0 || targetIndex >= fields.length) return form;

        const [field] = fields.splice(index, 1);
        fields.splice(targetIndex, 0, field);

        return { ...form, fields };
      }

      const sectionsCopy = sections.map((section) => ({
        ...section,
        fields: [...(section.fields || [])],
      }));
      const fields = sectionsCopy[sectionIndex].fields;
      const index = fields.findIndex((field) => field.id === fieldId);
      const targetIndex = direction === "up" ? index - 1 : index + 1;

      if (index < 0) return form;

      if (targetIndex < 0) {
        const previousSection = sectionsCopy[sectionIndex - 1];
        if (!previousSection) return form;

        const [field] = fields.splice(index, 1);
        previousSection.fields = [...(previousSection.fields || []), field];

        return { ...form, sections: sectionsCopy };
      }

      if (targetIndex >= fields.length) {
        const nextSection = sectionsCopy[sectionIndex + 1];
        if (!nextSection) return form;

        const [field] = fields.splice(index, 1);
        nextSection.fields = [field, ...(nextSection.fields || [])];

        return { ...form, sections: sectionsCopy };
      }

      const [field] = fields.splice(index, 1);
      fields.splice(targetIndex, 0, field);

      return { ...form, sections: sectionsCopy };
    });
  };

  const duplicateFormField = (fieldId) => {
    updateActiveForm((form) => {
      const cloneField = (field) => ({
        ...cloneWithNewIds(field),
        label: `${field.label || "Question"} Copy`,
      });

      const rootField = (form.fields || []).find((field) => field.id === fieldId);

      if (rootField) {
        const fields = [...(form.fields || [])];
        const fieldIndex = fields.findIndex((item) => item.id === fieldId);
        fields.splice(fieldIndex + 1, 0, cloneField(rootField));
        return {
          ...form,
          fields,
        };
      }

      return {
        ...form,
        sections: getFormSections(form).map((section) => {
          const fields = [...(section.fields || [])];
          const fieldIndex = fields.findIndex((item) => item.id === fieldId);
          if (fieldIndex < 0) return section;
          fields.splice(fieldIndex + 1, 0, cloneField(fields[fieldIndex]));
          return { ...section, fields };
        }),
      };
    });
  };

  const deleteFormField = (fieldId) => {
    updateActiveForm((form) => ({
      ...form,
      fields: (form.fields || []).filter((field) => field.id !== fieldId),
      sections: getFormSections(form).map((section) => ({
        ...section,
        fields: (section.fields || []).filter((field) => field.id !== fieldId),
      })),
    }));
  };

  const deleteFormSection = (sectionId) => {
    updateActiveForm((form) => ({
      ...form,
      sections: getFormSections(form).filter((section) => section.id !== sectionId),
    }));
  };

  return {
    addForm,
    deleteActiveForm,
    addFormSection,
    addFieldToForm,
    updateActiveFormQuiz,
    updateFormField,
    updateFormSection,
    moveFormField,
    duplicateFormField,
    deleteFormField,
    deleteFormSection,
  };
};
