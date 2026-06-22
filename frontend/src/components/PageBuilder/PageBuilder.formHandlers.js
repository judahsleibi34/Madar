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

  const addFormSection = () => {
    const section = {
      id: createId("formSection"),
      title: `Section ${getFormSections(activeForm).length + 1}`,
      description: "",
      collapsed: false,
      fields: [],
    };

    updateActiveForm((form) => ({
      ...form,
      sections: [...getFormSections(form), section],
    }));
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

      if (index < 0 || targetIndex < 0 || targetIndex >= fields.length) return form;

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
        return {
          ...form,
          fields: [...(form.fields || []), cloneField(rootField)],
        };
      }

      return {
        ...form,
        sections: getFormSections(form).map((section) => {
          const field = (section.fields || []).find((item) => item.id === fieldId);
          return field
            ? { ...section, fields: [...(section.fields || []), cloneField(field)] }
            : section;
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
