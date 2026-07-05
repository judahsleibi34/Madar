const digitalizationAboutContent = {
  hero: {
    eyebrow: "About Madar",
    title: "About Madar",
    titlePrefix: "About",
    titleHighlight: "Madar",
    name: "Madar",
    description:
      "helps organizations replace paper forms, scattered files, and manual follow-ups with clear digital workflows that teams can manage from one place.",
    secondDescription:
      "It is built for teams that want to modernize daily operations without losing the way they already work. Madar turns requests, approvals, records, users, and internal processes into organized digital systems that are easier to track, update, and grow.",
  },
  metrics: [
    {
      value: "Paperless",
      label: "Move forms, records, and approvals into one digital workspace.",
    },
    {
      value: "Connected",
      label: "Keep teams, requests, files, and decisions linked together.",
    },
    {
      value: "Flexible",
      label: "Shape pages, workflows, and data around how your organization works.",
    },
  ],
  sections: [
    {
      title: "Digitize the Work You Already Do",
      body:
        "Madar helps your organization turn printed forms, notebooks, spreadsheets, and repeated manual steps into structured digital workflows. Your team can collect information, follow requests, manage approvals, and keep important records in a cleaner, more reliable workspace.",
    },
    {
      title: "Built for Real Operations",
      body:
        "Every organization has its own departments, services, forms, and approval paths. Madar gives you the flexibility to shape the system around those needs, so your digital workspace feels practical for your team instead of forcing everyone into a rigid process.",
    },
    {
      title: "A Smarter Way to Manage Growth",
      body:
        "By keeping information connected, searchable, and easier to update, Madar helps teams save time, reduce mistakes, respond faster, and make better decisions. It gives your organization a strong digital foundation for smoother work today and more scalable operations tomorrow.",
    },
  ],
  closing:
    "Madar is not just about replacing paper with screens. It is about giving your organization a clearer way to work, communicate, and manage information with confidence.",
};

export const aboutContent = {
  en: digitalizationAboutContent,
  ar: digitalizationAboutContent,
};

export const getAboutContent = (lang = "en") =>
  aboutContent[lang === "ar" ? "ar" : "en"];
