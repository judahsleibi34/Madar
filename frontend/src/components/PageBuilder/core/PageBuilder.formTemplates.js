import { getFormTemplateContent } from "../../../content/pageBuilder";
import { createField, createFormSection } from "./PageBuilder.factories";

const templateField = ({ label, type = "shortText", ...overrides }) =>
  createField(label, type, overrides);

const buildFormTemplates = (lang = "en") =>
  getFormTemplateContent(lang).map((template) => ({
    ...template,
    fields: template.fields.map(templateField),
  }));

export const FORM_TEMPLATES = buildFormTemplates("en");

export const applyFormTemplate = (form, templateId) => {
  const template = FORM_TEMPLATES.find((item) => item.id === templateId);
  if (!template) return form;
  const fields = template.fields.map(({ id, ...field }) =>
    createField(field.label, field.type, field)
  );

  return {
    ...form,
    title: template.title,
    description: template.description,
    localized: {
      ...(form.localized || {}),
      title: { en: template.title },
      description: { en: template.description },
    },
    sections: [createFormSection("Page 1", fields)],
  };
};
