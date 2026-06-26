export const mainBuilderHiddenTabs = ["data", "responses"];

export const builderWorkspaceCopy = {
  en: {
    projectNames: {
      "Madar Builder Demo": "Madar Builder Demo",
    },
    topbar: {
      templates: "Templates",
      preview: "Preview site",
      exitPreview: "Exit site preview",
      save: "Save builder",
      goLive: "Publish site",
    },
    tabs: {
      design: {
        label: "Pages",
        helper: "Design screens, sections, layout, and visual elements.",
      },
      forms: {
        label: "Forms",
        helper: "Create forms and place them on pages.",
      },
      users: {
        label: "Users",
        helper: "Manage team members, roles, and permissions.",
      },
      theme: {
        label: "Themes",
        helper: "Control global colors, typography, spacing, and radius.",
      },
      publish: {
        label: "Publish",
        helper: "Preview, save, export, and publish the builder site.",
      },
      responses: {
        label: "Responses",
        helper: "Review submitted form answers.",
      },
      data: {
        label: "Data",
        helper: "Review, clean, and analyze your collected data.",
      },
    },
  },
  ar: {
    projectNames: {
      "Madar Builder Demo": "عرض منشئ مدار",
    },
    topbar: {
      templates: "القوالب",
      preview: "معاينة",
      exitPreview: "إنهاء المعاينة",
      save: "حفظ",
      goLive: "نشر",
    },
    tabs: {
      design: {
        label: "الصفحات",
        helper: "صمم الشاشات والأقسام والتخطيط والعناصر المرئية.",
      },
      forms: {
        label: "النماذج",
        helper: "أنشئ النماذج وضعها داخل الصفحات.",
      },
      users: {
        label: "المستخدمون",
        helper: "أدر أعضاء الفريق والأدوار والصلاحيات.",
      },
      theme: {
        label: "الثيم",
        helper: "تحكم في الألوان والخطوط والمسافات والزوايا.",
      },
      publish: {
        label: "النشر",
        helper: "عاين واحفظ وصدّر JSON وانشر الحالة.",
      },
      responses: {
        label: "الردود",
        helper: "راجع إجابات النماذج المرسلة.",
      },
      data: {
        label: "البيانات",
        helper: "راجع ونظف وحلل البيانات التي تم جمعها.",
      },
    },
  },
};

export const mobileBlockerCopy = {
  en: {
    design: {
      title: "Desktop builder only",
      message:
        "The page builder is designed for tablet and desktop editing. Use a wider screen to build layouts, forms, workflows, and themes comfortably.",
    },
    data: {
      title: "Data workspace needs more room",
      message:
        "Data review, cleaning, and reporting are designed for tablet and desktop screens. Use a wider screen to inspect tables and generate reports comfortably.",
    },
    responses: {
      title: "Submissions are easier on a wider screen",
      message:
        "Response review is designed for tablet and desktop screens. Use a wider screen to scan submissions, compare answers, and export data comfortably.",
    },
    default: {
      title: "Desktop workspace only",
      message:
        "This workspace is designed for tablet and desktop screens. Use a wider screen for the best editing experience.",
    },
  },
  ar: {
    design: {
      title: "المنشئ مخصص للشاشات الكبيرة",
      message:
        "منشئ الصفحات مصمم للتحرير على الأجهزة اللوحية وشاشات سطح المكتب. استخدم شاشة أوسع لبناء الصفحات والنماذج وسير العمل والثيمات بسهولة.",
    },
    data: {
      title: "مساحة البيانات تحتاج شاشة أوسع",
      message:
        "مراجعة البيانات وتنظيفها وإنشاء التقارير مصممة للأجهزة اللوحية وشاشات سطح المكتب. استخدم شاشة أوسع لقراءة الجداول والعمل براحة.",
    },
    responses: {
      title: "مراجعة الردود أسهل على شاشة أوسع",
      message:
        "مراجعة الردود مصممة للأجهزة اللوحية وشاشات سطح المكتب. استخدم شاشة أوسع لمقارنة الإجابات وتصدير البيانات براحة.",
    },
    default: {
      title: "مساحة العمل مخصصة للشاشات الكبيرة",
      message:
        "مساحة العمل هذه مصممة للأجهزة اللوحية وشاشات سطح المكتب. استخدم شاشة أوسع للحصول على أفضل تجربة.",
    },
  },
};

export const templateModalText = {
  en: {
    eyebrow: "Template library",
    title: "Choose a builder template",
    description:
      "Start from a focused operating system, then edit pages, forms, data, roles, workflows, and theme values.",
    close: "Close",
  },
  ar: {
    eyebrow: "مكتبة القوالب",
    title: "اختر قالبا للمنشئ",
    description:
      "ابدأ من نظام عمل جاهز، ثم عدل الصفحات والنماذج والبيانات والأدوار وسير العمل والثيم.",
    close: "إغلاق",
  },
};

export const starterArabicText = {
  showcase: {
    category: "تجربة",
    title: "عرض شامل للمنشئ",
    subtitle: "قالب افتراضي كامل يعرض الصفحات والنماذج والبيانات والوسائط وتسجيل الدخول وسير العمل.",
    tags: ["كل الميزات", "تجربة"],
  },
  cms: {
    category: "إدارة محتوى",
    title: "مركز إدارة المحتوى",
    subtitle: "صفحات تحريرية، نماذج استقبال، سير نشر، سجلات محتوى، وأدوار فريق.",
    tags: ["محتوى", "نشر", "موافقات"],
  },
  ecommerce: {
    category: "تجارة",
    title: "واجهة متجر إلكتروني",
    subtitle: "عرض منتجات، استقبال طلبات، سجلات عملاء، حالة تنفيذ، وعمليات جاهزة للحجز.",
    tags: ["منتجات", "طلبات", "عملاء"],
  },
  hrFinance: {
    category: "عمليات",
    title: "بوابة الموارد البشرية والمالية",
    subtitle: "طلبات موظفين، موافقات ميزانية، تعويضات، دعم رواتب، ومراجعة حسب الأدوار.",
    tags: ["موارد بشرية", "مالية", "موافقات"],
  },
  meal: {
    category: "مشاريع",
    title: "تنسيق مشاريع المتابعة والتقييم",
    subtitle: "متابعة وتقييم ومساءلة وتعلم وتقارير ميدانية ومؤشرات ومتابعة الشركاء.",
    tags: ["متابعة وتقييم", "مشاريع", "تقارير"],
  },
  blankPage: {
    title: "صفحة فارغة",
    subtitle: "ابدأ بصفحة واحدة فارغة تماماً.",
  },
  website: {
    title: "موقع ونموذج تواصل",
    subtitle: "موقع، نموذج تواصل، ردود، وأدوار أساسية.",
  },
  requests: {
    title: "بوابة طلبات وموافقات",
    subtitle: "موارد بشرية ومالية ومشتريات وموافقات داخلية.",
  },
  reports: {
    title: "مركز متابعة وتقارير",
    subtitle: "تقارير نشاط ولوحات متابعة وسير مراجعة.",
  },
  orders: {
    title: "نظام طلبات وحجوزات",
    subtitle: "طلبات عملاء وحجوزات خدمات وتتبع حالة.",
  },
  blank: {
    title: "نظام فارغ مخصص",
    subtitle: "ابدأ من صفحة واحدة ونموذج واحد ودور مدير.",
  },
};

export const internalPageNames = new Set([
  "review responses",
  "responses",
  "reports",
  "orders",
  "submit request",
  "submit report",
  "place order",
]);
