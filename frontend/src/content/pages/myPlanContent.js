export const myPlanContent = {
  en: {
    eyebrow: "Subscription",
    title: "Manage your plan",
    subtitle:
      "Review your current Madar plan, monitor usage, and see which modules are active in your workspace.",
    manageBilling: "Manage billing",
    upgradePlan: "Upgrade plan",
    currentPlan: "Current plan",
    perMonth: "/ month",
    billingCycle: "Billing",
    renewsOn: "Renews on",
    users: "Users",
    workspace: "Workspace",
    recommendationLabel: "Recommended",
    recommendationTitle: "Your workspace is growing",
    recommendationText:
      "You are using the main operational tools. Upgrade when you need more submissions, team members, data analysis, or advanced workflows.",
    recommendationPoints: [
      "Higher website, form, and response limits",
      "Advanced data analysis and reports",
      "More role-based workflow controls",
      "Priority support and custom domain options",
    ],
    viewUpgrade: "View upgrade options",
    usageLabel: "Usage",
    usageTitle: "Current usage",
    usageSubtitle:
      "Track the limits that matter most to your workspace. High usage means your platform is becoming business-critical.",
    modulesLabel: "Modules",
    modulesTitle: "Workspace modules",
    modulesSubtitle:
      "Enabled modules are included in your plan. Locked modules can be unlocked through upgrade or custom plan.",
    enabled: "Enabled",
    locked: "Locked",
    enabledModule: "Available module",
    lockedModule: "Upgrade module",
    modulePrice: "Module price",
    openModule: "Open module",
    unlockModule: "Unlock module",
    plan: {
      name: "Operations",
      status: "Active",
      price: "$29",
      billingCycle: "Monthly",
      renewsOn: "February 15, 2026",
      users: "3 users",
      workspace: "Main workspace",
      description:
        "Operations is built for teams that publish pages, collect forms, manage requests, track submissions, and run daily customer workflows.",
    },
    usage: [
      {
        label: "Published websites",
        value: 2,
        max: 3,
        note: "Use websites for your main brand, services, and public portals.",
      },
      {
        label: "Active forms",
        value: 14,
        max: 25,
        note: "Forms collect requests, bookings, reports, approvals, and orders.",
      },
      {
        label: "Monthly submissions",
        value: 1840,
        max: 5000,
        note: "Every submission can become a lead, request, order, or data point.",
      },
      {
        label: "Workspace users",
        value: 2,
        max: 3,
        note: "Add team members when your workflow needs shared ownership.",
      },
    ],
    modules: [
      {
        id: "website",
        name: "Website Builder",
        price: "Included",
        enabled: true,
        description:
          "Create and publish branded pages, service pages, contact pages, and public portals.",
        value:
          "Keeps your business visible and lets customers access your forms and pages online.",
      },
      {
        id: "forms",
        name: "Forms & Responses",
        price: "Included",
        enabled: true,
        description:
          "Build forms, collect submissions, search responses, and manage status updates.",
        value:
          "Turns visitors and customers into structured requests, bookings, approvals, and reports.",
      },
      {
        id: "requests",
        name: "Requests Portal",
        price: "Included",
        enabled: true,
        description:
          "Manage submissions as trackable requests with statuses and follow-up.",
        value:
          "Helps your team organize customer and internal work instead of losing requests in messages.",
      },
      {
        id: "data",
        name: "Data Analysis Workspace",
        price: "$39 / month",
        enabled: false,
        description:
          "Upload data files, inspect datasets, clean data, and generate analysis reports.",
        value:
          "Best when your team needs quality reports, missing-values checks, statistics, and visual analysis.",
      },
      {
        id: "reports",
        name: "Reports Hub",
        price: "$29 / month",
        enabled: false,
        description:
          "Create professional reports from responses, data, projects, operations, and KPIs.",
        value:
          "Useful for sharing results with managers, clients, donors, or partners.",
      },
      {
        id: "workflows",
        name: "Advanced Workflows",
        price: "$49 / month",
        enabled: false,
        description:
          "Create internal workflows for approvals, HR, finance, MEAL projects, roles, and permissions.",
        value:
          "Best for organizations with multi-step processes and role-based access.",
      },
    ],
  },

  ar: {
    eyebrow: "الاشتراك",
    title: "إدارة خطتك",
    subtitle:
      "راجع خطة Madar الحالية، راقب الاستخدام، وتابع الوحدات المفعلة في مساحة العمل.",
    manageBilling: "إدارة الفوترة",
    upgradePlan: "ترقية الخطة",
    currentPlan: "الخطة الحالية",
    perMonth: "/ شهر",
    billingCycle: "الفوترة",
    renewsOn: "تتجدد في",
    users: "المستخدمون",
    workspace: "مساحة العمل",
    recommendationLabel: "موصى به",
    recommendationTitle: "مساحة العمل تنمو",
    recommendationText:
      "أنت تستخدم أدوات التشغيل الأساسية. قم بالترقية عندما تحتاج إلى ردود أكثر، مستخدمين أكثر، تحليل بيانات، أو تدفقات عمل متقدمة.",
    recommendationPoints: [
      "حدود أعلى للمواقع والنماذج والردود",
      "تحليل بيانات وتقارير متقدمة",
      "تحكم أكبر بالصلاحيات وتدفقات العمل",
      "دعم بأولوية وخيارات نطاق مخصص",
    ],
    viewUpgrade: "عرض خيارات الترقية",
    usageLabel: "الاستخدام",
    usageTitle: "الاستخدام الحالي",
    usageSubtitle:
      "تابع الحدود الأهم لمساحة العمل. الاستخدام العالي يعني أن المنصة أصبحت جزءاً أساسياً من التشغيل.",
    modulesLabel: "الوحدات",
    modulesTitle: "وحدات مساحة العمل",
    modulesSubtitle:
      "الوحدات المفعلة مشمولة في خطتك. الوحدات المقفلة يمكن فتحها من خلال الترقية أو خطة مخصصة.",
    enabled: "مفعلة",
    locked: "مقفلة",
    enabledModule: "وحدة متاحة",
    lockedModule: "تحتاج ترقية",
    modulePrice: "سعر الوحدة",
    openModule: "فتح الوحدة",
    unlockModule: "فتح بالترقية",
    plan: {
      name: "Operations",
      status: "نشطة",
      price: "$29",
      billingCycle: "شهرية",
      renewsOn: "15 فبراير 2026",
      users: "3 مستخدمين",
      workspace: "مساحة العمل الرئيسية",
      description:
        "خطة Operations مصممة للفرق التي تنشر الصفحات، تجمع النماذج، تدير الطلبات، تتابع الردود، وتشغل سير عمل العملاء اليومي.",
    },
    usage: [
      {
        label: "المواقع المنشورة",
        value: 2,
        max: 3,
        note: "استخدم المواقع لعلامتك التجارية، خدماتك، والبوابات العامة.",
      },
      {
        label: "النماذج النشطة",
        value: 14,
        max: 25,
        note: "النماذج تجمع الطلبات، الحجوزات، التقارير، الموافقات، والأوامر.",
      },
      {
        label: "الردود الشهرية",
        value: 1840,
        max: 5000,
        note: "كل رد يمكن أن يصبح عميلاً محتملاً، طلباً، أمراً، أو نقطة بيانات.",
      },
      {
        label: "مستخدمو مساحة العمل",
        value: 2,
        max: 3,
        note: "أضف أعضاء الفريق عندما يحتاج سير العمل إلى مشاركة المسؤولية.",
      },
    ],
    modules: [
      {
        id: "website",
        name: "منشئ المواقع",
        price: "مشمول",
        enabled: true,
        description:
          "أنشئ وانشر صفحات بعلامتك التجارية، صفحات خدمات، صفحات تواصل، وبوابات عامة.",
        value:
          "يحافظ على حضور عملك ويسمح للعملاء بالوصول إلى النماذج والصفحات عبر الإنترنت.",
      },
      {
        id: "forms",
        name: "النماذج والردود",
        price: "مشمول",
        enabled: true,
        description:
          "ابنِ النماذج، اجمع الردود، ابحث في الردود، وأدر تحديثات الحالة.",
        value:
          "يحول الزوار والعملاء إلى طلبات، حجوزات، موافقات، وتقارير منظمة.",
      },
      {
        id: "requests",
        name: "بوابة الطلبات",
        price: "مشمول",
        enabled: true,
        description:
          "أدر الردود كطلبات قابلة للمتابعة مع الحالات والمتابعة.",
        value:
          "يساعد فريقك على تنظيم طلبات العملاء والطلبات الداخلية بدلاً من فقدانها في الرسائل.",
      },
      {
        id: "data",
        name: "مساحة تحليل البيانات",
        price: "$39 / شهر",
        enabled: false,
        description:
          "ارفع ملفات البيانات، افحص البيانات، نظف البيانات، وأنشئ تقارير تحليل.",
        value:
          "مناسب عندما يحتاج الفريق إلى تقارير جودة، فحص القيم الناقصة، الإحصاءات، والتحليل البصري.",
      },
      {
        id: "reports",
        name: "مركز التقارير",
        price: "$29 / شهر",
        enabled: false,
        description:
          "أنشئ تقارير احترافية من الردود، البيانات، المشاريع، التشغيل، والمؤشرات.",
        value:
          "مفيد لمشاركة النتائج مع الإدارة، العملاء، الممولين، أو الشركاء.",
      },
      {
        id: "workflows",
        name: "تدفقات العمل المتقدمة",
        price: "$49 / شهر",
        enabled: false,
        description:
          "أنشئ تدفقات عمل داخلية للموافقات، الموارد البشرية، المالية، مشاريع MEAL، الأدوار، والصلاحيات.",
        value:
          "مناسب للمؤسسات التي لديها عمليات متعددة الخطوات وصلاحيات حسب الدور.",
      },
    ],
  },
};

export const getMyPlanContent = (lang = "en") =>
  myPlanContent[lang === "ar" ? "ar" : "en"];