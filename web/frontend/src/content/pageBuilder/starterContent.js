export const starterContent = {
  en: {
    sectionLibrary: [
      {
        id: "hero",
        title: "Hero Section",
        category: "Website",
        description: "Headline, text, button, and card.",
      },
      {
        id: "login",
        title: "Login Section",
        category: "Auth",
        description: "Login page block for private/internal website areas.",
      },
      {
        id: "form",
        title: "Form Section",
        category: "Forms",
        description: "Place the active form on the page.",
      },
      {
        id: "metrics",
        title: "Metrics Section",
        category: "Dashboard",
        description: "Counters for responses and statuses.",
      },
    ],
    defaults: {
      heroButton: "Fill the form",
      heroCard:
        "Madar App Builder\nPages, forms, data, workflows, users, and publishing in one front-end builder.",
      responsesHeading: "Responses",
      loginHeading: "Login to your account",
      loginText:
        "Access your private dashboard, submissions, reports, and internal tools.",
      loginCard: "Email address\nPassword\nLogin",
      metrics: {
        totalResponses: "Total Responses\n128",
        pending: "Pending\n24",
        approved: "Approved\n86",
        rejected: "Rejected\n18",
        openItems: "Open items\n24",
        readyForReview: "Ready for review\n8",
      },
      industryCta: "Submit request",
    },
  },
};

starterContent.ar = starterContent.en;

export function getStarterContent(lang = "en") {
  return starterContent[lang] || starterContent.en;
}
