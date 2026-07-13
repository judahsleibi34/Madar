export const pricingContent = {
  en: {
    eyebrow: "Pricing",
    header: "Choose a monthly plan",
    subheader:
      "Select the tools your business needs and see the matching plan.",

    basePlansTab: "Plans",
    customPlansTab: "Plans",

    basePlansLabel: "Plans",
    basePlansTitle: "Choose your tools",
    basePlansSubtitle:
      "Start with the modules you need now. You can move to a larger plan later.",

    recommended: "Recommended",
    bestFor: "Good for",
    workflow: "How it helps",
    includes: "What you get",
    perMonth: "/ month",
    chooserTitle: "Plan options",
    chooserSubtitle:
      "Turn modules on or off to find the right monthly plan. Reservations include the website CMS because customers need a public page to book from.",
    yourPlan: "Selected plan",
    comparePlans: "Compare all plans",
    includedInPlan: "Included in this plan",
    reservationNeedsCms:
      "CMS is included with reservations so customers can book from a public page.",
    saving: "Saving...",
    success: "Subscription request saved. Payment setup is not connected yet.",
    requestSaved: "Your access request was saved. No payment was taken.",
    requestTitle: "Access request saved",
    availabilityNotice:
      "Online checkout is coming soon. Requesting a plan records your interest for manual follow-up and does not charge you.",
    loginRequired: "Please log in before choosing a plan.",
    serverError: "Could not connect to server.",

    basePlans: [
      {
        id: "cms",
        billingPlan: "cms",
        name: "CMS Builder",
        badge: "CMS only",
        price: "$15",
        recommended: false,
        cta: "Request CMS access",
        description:
          "For a website you can update yourself without forms, analysis, or bookings.",
        bestFor:
          "Service pages, landing pages, company profiles, and regular content updates.",
        workflow:
          "Edit pages, publish updates, and manage website content from one workspace.",
        includes: [
          "Website builder and CMS",
          "Publish pages online",
          "Edit text, sections, and theme settings",
          "Workspace access",
        ],
        features: [
          { text: "Build and update website pages", included: true },
          { text: "Manage content from your workspace", included: true },
          { text: "Forms and response tracking", included: false },
          { text: "Data Analysis page", included: false },
          { text: "Reservations", included: false },
        ],
      },
      {
        id: "forms-data",
        billingPlan: "forms_data",
        name: "Forms + DA",
        badge: "Forms and analysis",
        price: "$10",
        recommended: false,
        cta: "Request Forms + DA access",
        description:
          "For collecting information and reviewing it without a full website.",
        bestFor:
          "Surveys, requests, internal forms, uploaded files, and simple reports.",
        workflow:
          "Create forms, collect responses, then clean and review the data in the analysis page.",
        includes: [
          "Forms builder",
          "Responses dashboard",
          "Data Analysis page",
          "Workspace access",
        ],
        features: [
          { text: "Create forms and collect answers", included: true },
          { text: "Review and search responses", included: true },
          { text: "Use the Data Analysis page", included: true },
          { text: "Website CMS", included: false },
          { text: "Reservations", included: false },
        ],
      },
      {
        id: "cms-plus",
        billingPlan: "cms_plus",
        name: "CMS Plus",
        badge: "CMS + one module",
        price: "$20",
        recommended: true,
        cta: "Request CMS Plus access",
        description:
          "For a website plus one extra workflow: forms or reservations.",
        bestFor:
          "Small teams that need a public website with either requests or bookings.",
        workflow:
          "Run your website and let visitors submit forms or make reservations.",
        includes: [
          "Website builder and CMS",
          "Choose forms or reservations",
          "Published pages",
          "Workspace access",
        ],
        features: [
          { text: "Build and update website pages", included: true },
          { text: "Use forms with Data Analysis, or use reservations", included: true },
          { text: "Keep customer activity in one workspace", included: true },
          { text: "All tools together", included: false },
        ],
      },
      {
        id: "complete",
        billingPlan: "complete",
        name: "Complete",
        badge: "CMS + forms + reservations",
        price: "$25",
        recommended: false,
        cta: "Request Complete access",
        description:
          "For teams that need the full setup: website, forms, analysis, and reservations.",
        bestFor:
          "Businesses that want one place for their site, customer data, files, and bookings.",
        workflow:
          "Run the website, collect forms, review data, manage reservations, and keep files organized.",
        includes: [
          "Website builder and CMS",
          "Forms and Data Analysis",
          "Reservations",
          "File saving locally or on the server",
        ],
        features: [
          { text: "Build and update website pages", included: true },
          { text: "Create forms and analyze responses", included: true },
          { text: "Manage reservations", included: true },
          { text: "Save files on your device or keep them on the server", included: true },
          { text: "Use all main Madar tools together", included: true },
        ],
      },
    ],

    modules: [
      {
        id: "cms",
        name: "Website CMS",
        shortName: "CMS",
        description: "Build pages and update website content.",
      },
      {
        id: "forms",
        name: "Forms + Data Analysis",
        shortName: "Forms + DA",
        description: "Collect answers, review responses, and analyze data.",
      },
      {
        id: "reservations",
        name: "Reservations",
        shortName: "Reservations",
        description: "Let customers book or request a time.",
      },
    ],

    customPlans: {
      label: "Plans",
      title: "Static monthly plans",
      subtitle:
        "Madar now uses fixed plans based on the modules you need.",
      summaryLabel: "Selected plan",
      summaryTitle: "Fixed package",
      summaryText:
        "Choose one of the static monthly plans instead of building a custom package.",
      estimatedPrice: "Monthly price",
      selectedModules: "Included modules",
      noModules: "No modules selected.",
      requestPlan: "Choose a plan",
      note: "For special limits or integrations, contact the Madar team.",
      modules: [],
    },
  },

  ar: {
    eyebrow: "Pricing",
    header: "Choose a monthly plan",
    subheader:
      "Select the tools your business needs and see the matching plan.",

    basePlansTab: "Plans",
    customPlansTab: "Plans",

    basePlansLabel: "Plans",
    basePlansTitle: "Choose your tools",
    basePlansSubtitle:
      "Start with the modules you need now. You can move to a larger plan later.",

    recommended: "Recommended",
    bestFor: "Good for",
    workflow: "How it helps",
    includes: "What you get",
    perMonth: "/ month",
    chooserTitle: "Plan options",
    chooserSubtitle:
      "Turn modules on or off to find the right monthly plan. Reservations include the website CMS because customers need a public page to book from.",
    yourPlan: "Selected plan",
    comparePlans: "Compare all plans",
    includedInPlan: "Included in this plan",
    reservationNeedsCms:
      "CMS is included with reservations so customers can book from a public page.",
    saving: "Saving...",
    success: "Subscription request saved. Payment setup is not connected yet.",
    requestSaved: "تم حفظ طلب الوصول. لم يتم تحصيل أي دفعة.",
    requestTitle: "تم حفظ طلب الوصول",
    availabilityNotice:
      "الدفع الإلكتروني سيتوفر قريباً. طلب الخطة يسجل اهتمامك للمتابعة اليدوية ولا يخصم أي مبلغ.",
    loginRequired: "Please log in before choosing a plan.",
    serverError: "Could not connect to server.",

    basePlans: [
      {
        id: "cms",
        billingPlan: "cms",
        name: "CMS Builder",
        badge: "CMS only",
        price: "$15",
        recommended: false,
        cta: "طلب الوصول إلى CMS",
        description:
          "For a website you can update yourself without forms, analysis, or bookings.",
        bestFor:
          "Service pages, landing pages, company profiles, and regular content updates.",
        workflow:
          "Edit pages, publish updates, and manage website content from one workspace.",
        includes: [
          "Website builder and CMS",
          "Publish pages online",
          "Edit text, sections, and theme settings",
          "Workspace access",
        ],
        features: [
          { text: "Build and update website pages", included: true },
          { text: "Manage content from your workspace", included: true },
          { text: "Forms and response tracking", included: false },
          { text: "Data Analysis page", included: false },
          { text: "Reservations", included: false },
        ],
      },
      {
        id: "forms-data",
        billingPlan: "forms_data",
        name: "Forms + DA",
        badge: "Forms and analysis",
        price: "$10",
        recommended: false,
        cta: "طلب الوصول إلى النماذج والتحليل",
        description:
          "For collecting information and reviewing it without a full website.",
        bestFor:
          "Surveys, requests, internal forms, uploaded files, and simple reports.",
        workflow:
          "Create forms, collect responses, then clean and review the data in the analysis page.",
        includes: [
          "Forms builder",
          "Responses dashboard",
          "Data Analysis page",
          "Workspace access",
        ],
        features: [
          { text: "Create forms and collect answers", included: true },
          { text: "Review and search responses", included: true },
          { text: "Use the Data Analysis page", included: true },
          { text: "Website CMS", included: false },
          { text: "Reservations", included: false },
        ],
      },
      {
        id: "cms-plus",
        billingPlan: "cms_plus",
        name: "CMS Plus",
        badge: "CMS + one module",
        price: "$20",
        recommended: true,
        cta: "طلب الوصول إلى CMS Plus",
        description:
          "For a website plus one extra workflow: forms or reservations.",
        bestFor:
          "Small teams that need a public website with either requests or bookings.",
        workflow:
          "Run your website and let visitors submit forms or make reservations.",
        includes: [
          "Website builder and CMS",
          "Choose forms or reservations",
          "Published pages",
          "Workspace access",
        ],
        features: [
          { text: "Build and update website pages", included: true },
          { text: "Use forms with Data Analysis, or use reservations", included: true },
          { text: "Keep customer activity in one workspace", included: true },
          { text: "All tools together", included: false },
        ],
      },
      {
        id: "complete",
        billingPlan: "complete",
        name: "Complete",
        badge: "CMS + forms + reservations",
        price: "$25",
        recommended: false,
        cta: "طلب الوصول إلى الخطة الكاملة",
        description:
          "For teams that need the full setup: website, forms, analysis, and reservations.",
        bestFor:
          "Businesses that want one place for their site, customer data, files, and bookings.",
        workflow:
          "Run the website, collect forms, review data, manage reservations, and keep files organized.",
        includes: [
          "Website builder and CMS",
          "Forms and Data Analysis",
          "Reservations",
          "File saving locally or on the server",
        ],
        features: [
          { text: "Build and update website pages", included: true },
          { text: "Create forms and analyze responses", included: true },
          { text: "Manage reservations", included: true },
          { text: "Save files on your device or keep them on the server", included: true },
          { text: "Use all main Madar tools together", included: true },
        ],
      },
    ],

    modules: [
      {
        id: "cms",
        name: "Website CMS",
        shortName: "CMS",
        description: "Build pages and update website content.",
      },
      {
        id: "forms",
        name: "Forms + Data Analysis",
        shortName: "Forms + DA",
        description: "Collect answers, review responses, and analyze data.",
      },
      {
        id: "reservations",
        name: "Reservations",
        shortName: "Reservations",
        description: "Let customers book or request a time.",
      },
    ],

    customPlans: {
      label: "Plans",
      title: "Static monthly plans",
      subtitle:
        "Madar now uses fixed plans based on the modules you need.",
      summaryLabel: "Selected plan",
      summaryTitle: "Fixed package",
      summaryText:
        "Choose one of the static monthly plans instead of building a custom package.",
      estimatedPrice: "Monthly price",
      selectedModules: "Included modules",
      noModules: "No modules selected.",
      requestPlan: "Choose a plan",
      note: "For special limits or integrations, contact the Madar team.",
      modules: [],
    },
  },
};

export const getPricingContent = (lang = "en") =>
  pricingContent[lang === "ar" ? "ar" : "en"];
