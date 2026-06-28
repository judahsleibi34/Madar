export const formTemplateContent = {
  en: [
    {
      id: "contact",
      label: "Contact form",
      title: "Contact form",
      description: "Collect contact details and a message.",
      fields: [
        { label: "Full name", type: "shortText", required: true },
        { label: "Email", type: "email", required: true },
        { label: "Phone", type: "shortText" },
        { label: "Message", type: "paragraph", required: true },
      ],
    },
    {
      id: "request",
      label: "Service request",
      title: "Service request",
      description: "Collect service needs, timing, and contact details.",
      fields: [
        { label: "Full name", type: "shortText", required: true },
        { label: "Contact number", type: "shortText", required: true },
        {
          label: "Service needed",
          type: "dropdown",
          required: true,
          options: ["Consultation", "Implementation", "Support", "Other"],
        },
        { label: "Preferred date", type: "date" },
        { label: "Request details", type: "paragraph", required: true },
      ],
    },
    {
      id: "registration",
      label: "Registration",
      title: "Registration form",
      description: "Register participants and collect preferences.",
      fields: [
        { label: "Full name", type: "shortText", required: true },
        { label: "Email", type: "email", required: true },
        { label: "Mobile number", type: "shortText", required: true },
        { label: "Attendance type", type: "radio", options: ["In person", "Online"] },
        { label: "Notes", type: "paragraph" },
      ],
    },
    {
      id: "application",
      label: "Application",
      title: "Application form",
      description: "Collect applicant information and supporting files.",
      fields: [
        { label: "Full name", type: "shortText", required: true },
        { label: "Email", type: "email", required: true },
        { label: "Role or program", type: "shortText", required: true },
        { label: "Experience summary", type: "paragraph" },
        {
          label: "Upload file",
          type: "file",
          helpText: "File storage requires backend integration.",
        },
      ],
    },
    {
      id: "feedback",
      label: "Feedback",
      title: "Feedback form",
      description: "Collect ratings, comments, and follow-up consent.",
      fields: [
        {
          label: "Overall rating",
          type: "radio",
          required: true,
          options: ["Excellent", "Good", "Average", "Poor"],
        },
        { label: "What worked well?", type: "paragraph" },
        { label: "What should improve?", type: "paragraph" },
        { label: "Can we contact you?", type: "radio", options: ["Yes", "No"] },
      ],
    },
  ],
};

formTemplateContent.ar = formTemplateContent.en;

export function getFormTemplateContent(lang = "en") {
  return formTemplateContent[lang] || formTemplateContent.en;
}
