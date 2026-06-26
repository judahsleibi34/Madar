import { createField, createFormSection } from "./PageBuilder.factories";

const templateField = (label, type = "shortText", overrides = {}) =>
  createField(label, type, overrides);

export const FORM_TEMPLATES = [
  {
    id: "contact",
    label: "Contact form",
    title: "Contact form",
    description: "Collect contact details and a message.",
    fields: [
      templateField("Full name", "shortText", { required: true }),
      templateField("Email", "email", { required: true }),
      templateField("Phone", "shortText"),
      templateField("Message", "paragraph", { required: true }),
    ],
  },
  {
    id: "request",
    label: "Service request",
    title: "Service request",
    description: "Collect service needs, timing, and contact details.",
    fields: [
      templateField("Full name", "shortText", { required: true }),
      templateField("Contact number", "shortText", { required: true }),
      templateField("Service needed", "dropdown", {
        required: true,
        options: ["Consultation", "Implementation", "Support", "Other"],
      }),
      templateField("Preferred date", "date"),
      templateField("Request details", "paragraph", { required: true }),
    ],
  },
  {
    id: "registration",
    label: "Registration",
    title: "Registration form",
    description: "Register participants and collect preferences.",
    fields: [
      templateField("Full name", "shortText", { required: true }),
      templateField("Email", "email", { required: true }),
      templateField("Mobile number", "shortText", { required: true }),
      templateField("Attendance type", "radio", {
        options: ["In person", "Online"],
      }),
      templateField("Notes", "paragraph"),
    ],
  },
  {
    id: "application",
    label: "Application",
    title: "Application form",
    description: "Collect applicant information and supporting files.",
    fields: [
      templateField("Full name", "shortText", { required: true }),
      templateField("Email", "email", { required: true }),
      templateField("Role or program", "shortText", { required: true }),
      templateField("Experience summary", "paragraph"),
      templateField("Upload file", "file", {
        helpText: "File storage requires backend integration.",
      }),
    ],
  },
  {
    id: "feedback",
    label: "Feedback",
    title: "Feedback form",
    description: "Collect ratings, comments, and follow-up consent.",
    fields: [
      templateField("Overall rating", "radio", {
        required: true,
        options: ["Excellent", "Good", "Average", "Poor"],
      }),
      templateField("What worked well?", "paragraph"),
      templateField("What should improve?", "paragraph"),
      templateField("Can we contact you?", "radio", {
        options: ["Yes", "No"],
      }),
    ],
  },
];

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
