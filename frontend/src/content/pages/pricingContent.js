export const pricingContent = {
  en: {
    eyebrow: "Pricing",
    header: "Choose a plan that matches how you work",
    subheader:
      "Start with a ready base plan, or build a custom Madar package around the exact website, form, data, reporting, and workflow tools your team needs.",

    basePlansTab: "Base plans",
    customPlansTab: "Custom plan",

    basePlansLabel: "Base plans",
    basePlansTitle: "Ready plans for common business needs",
    basePlansSubtitle:
      "Choose one of the standard plans if you want a clear package with fixed limits, fixed pricing, and a simple upgrade path.",

    recommended: "Recommended",
    bestFor: "Best for",
    workflow: "Workflow",
    includes: "Included limits",
    perMonth: "/ month",

    basePlans: [
      {
        id: "presence",
        name: "Presence",
        badge: "Website",
        price: "$9",
        recommended: false,
        cta: "Start with Presence",
        description:
          "For individuals and small projects that need a professional website and basic lead capture.",
        bestFor:
          "Brochure websites, service pages, personal brands, simple company websites, and contact forms.",
        workflow:
          "Build your website, publish your pages, and collect basic inquiries from visitors.",
        includes: [
          "1 published website",
          "5 active forms",
          "500 monthly submissions",
          "1 workspace user",
        ],
        features: [
          { text: "Website page builder", included: true },
          { text: "Home, About, Features, Pricing, Team, and Contact pages", included: true },
          { text: "English and Arabic public website", included: true },
          { text: "Light and dark theme switching", included: true },
          { text: "Basic contact forms", included: true },
          { text: "Website settings and public link", included: true },
          { text: "Responses dashboard", included: true },
          { text: "Requests portal", included: false },
          { text: "Data analysis workspace", included: false },
          { text: "Advanced reports", included: false },
        ],
      },
      {
        id: "operations",
        name: "Operations",
        badge: "Forms + Requests",
        price: "$29",
        recommended: true,
        cta: "Start with Operations",
        description:
          "For teams that need to collect requests, bookings, approvals, reports, and customer submissions.",
        bestFor:
          "Service businesses, clinics, agencies, schools, NGOs, operations teams, and support workflows.",
        workflow:
          "Publish pages and forms, collect submissions, track statuses, and manage follow-up.",
        includes: [
          "3 published websites",
          "25 active forms",
          "5,000 monthly submissions",
          "3 workspace users",
        ],
        features: [
          { text: "Everything in Presence", included: true },
          { text: "Advanced form builder", included: true },
          { text: "Requests, approvals, bookings, reports, and orders forms", included: true },
          { text: "Search responses by name, email, status, date, or field values", included: true },
          { text: "Submission status management", included: true },
          { text: "Public form links and QR previews", included: true },
          { text: "Basic reporting", included: true },
          { text: "Profile and website settings", included: true },
          { text: "Data analysis workspace", included: false },
          { text: "Advanced role-based workflows", included: false },
        ],
      },
      {
        id: "platform",
        name: "Platform",
        badge: "Full workspace",
        price: "$79",
        recommended: false,
        cta: "Start with Platform",
        description:
          "For organizations that want websites, forms, submissions, data analysis, reports, team roles, and workflows connected.",
        bestFor:
          "Growing companies, departments, NGOs, multi-service teams, and organizations running multiple digital operations.",
        workflow:
          "Build websites, collect data, manage responses, analyze datasets, create reports, and control team access.",
        includes: [
          "Unlimited websites",
          "Unlimited forms",
          "50,000 monthly submissions",
          "Unlimited workspace users",
        ],
        features: [
          { text: "Everything in Operations", included: true },
          { text: "Data file upload and dataset inspection", included: true },
          { text: "Preparation, quality, statistics, and missing-values reports", included: true },
          { text: "Cleaning actions and assisted analysis", included: true },
          { text: "Visualizations and report generation", included: true },
          { text: "CMS, ecommerce, HR/finance, and MEAL project templates", included: true },
          { text: "Advanced role-based access", included: true },
          { text: "Custom domain and priority support", included: true },
          { text: "Admin dashboard and platform activity", included: true },
          { text: "Custom integrations", included: false },
        ],
      },
    ],

    customPlans: {
      label: "Custom plan",
      title: "Build a plan around your exact workflow",
      subtitle:
        "Select the modules your team needs. The estimate updates instantly, then your team can request a tailored plan.",
      summaryLabel: "Your custom package",
      summaryTitle: "Selected modules",
      summaryText:
        "This estimate is based on selected modules. Final pricing can be adjusted for usage limits, team size, integrations, and support needs.",
      estimatedPrice: "Estimated monthly price",
      selectedModules: "Selected modules",
      noModules: "No modules selected yet.",
      requestPlan: "Request custom plan",
      note:
        "Custom plans are best when your team needs special limits, workflows, integrations, or admin controls.",
      modules: [
        {
          id: "website",
          name: "Website Builder",
          price: "$15",
          priceValue: 15,
          defaultSelected: true,
          description:
            "Create and publish branded websites, landing pages, service pages, and public portals.",
          value:
            "Best for public presence, service pages, marketing pages, and published business sites.",
        },
        {
          id: "forms",
          name: "Forms & Responses",
          price: "$19",
          priceValue: 19,
          defaultSelected: true,
          description:
            "Build forms, collect submissions, preview forms, search responses, and update statuses.",
          value:
            "Best for contact, requests, reservations, approvals, reports, orders, and quizzes.",
        },
        {
          id: "requests",
          name: "Requests Portal",
          price: "$19",
          priceValue: 19,
          defaultSelected: false,
          description:
            "Turn submissions into trackable requests with statuses, priorities, review, and follow-up.",
          value:
            "Best for operations teams that need to manage customer or internal requests.",
        },
        {
          id: "data",
          name: "Data Analysis Workspace",
          price: "$39",
          priceValue: 39,
          defaultSelected: false,
          description:
            "Upload files, inspect datasets, generate quality reports, clean data, and run analysis.",
          value:
            "Best for teams that work with spreadsheets, field data, reports, and performance metrics.",
        },
        {
          id: "reports",
          name: "Reports Hub",
          price: "$29",
          priceValue: 29,
          defaultSelected: false,
          description:
            "Create reports, visualizations, project summaries, operations reports, and performance pages.",
          value:
            "Best for teams that need to present results to managers, clients, partners, or donors.",
        },
        {
          id: "commerce",
          name: "Orders & Booking",
          price: "$24",
          priceValue: 24,
          defaultSelected: false,
          description:
            "Accept orders, reservations, service requests, consultations, and booking submissions.",
          value:
            "Best for service businesses that want customers to book or request online.",
        },
        {
          id: "cms",
          name: "CMS & Content",
          price: "$29",
          priceValue: 29,
          defaultSelected: false,
          description:
            "Manage reusable content collections such as services, projects, articles, resources, and directories.",
          value:
            "Best for larger sites that need structured and frequently updated content.",
        },
        {
          id: "workflows",
          name: "Advanced Workflows",
          price: "$49",
          priceValue: 49,
          defaultSelected: false,
          description:
            "Create internal workflows for approvals, HR, finance, MEAL projects, roles, and permissions.",
          value:
            "Best for organizations with multi-step processes and role-based team access.",
        },
      ],
    },
  },

  ar: {
    eyebrow: "الأسعار",
    header: "اختر خطة تناسب طريقة عملك",
    subheader:
      "ابدأ بخطة جاهزة، أو ابنِ باقة مخصصة حول أدوات الموقع، النماذج، البيانات، التقارير، وتدفقات العمل التي يحتاجها فريقك.",

    basePlansTab: "الخطط الأساسية",
    customPlansTab: "خطة مخصصة",

    basePlansLabel: "الخطط الأساسية",
    basePlansTitle: "خطط جاهزة لاحتياجات العمل الشائعة",
    basePlansSubtitle:
      "اختر إحدى الخطط القياسية إذا كنت تريد باقة واضحة بحدود ثابتة، سعر ثابت، ومسار ترقية بسيط.",

    recommended: "موصى بها",
    bestFor: "مناسب لـ",
    workflow: "تدفق العمل",
    includes: "الحدود المشمولة",
    perMonth: "/ شهر",

    basePlans: [
      {
        id: "presence",
        name: "Presence",
        badge: "موقع",
        price: "$9",
        recommended: false,
        cta: "ابدأ بخطة Presence",
        description:
          "للأفراد والمشاريع الصغيرة التي تحتاج إلى موقع احترافي وجمع استفسارات بسيط.",
        bestFor:
          "المواقع التعريفية، صفحات الخدمات، العلامات الشخصية، مواقع الشركات البسيطة، ونماذج التواصل.",
        workflow:
          "ابنِ موقعك، انشر الصفحات، واجمع الاستفسارات الأساسية من الزوار.",
        includes: [
          "موقع منشور واحد",
          "5 نماذج نشطة",
          "500 رد شهري",
          "مستخدم واحد",
        ],
        features: [
          { text: "منشئ صفحات الموقع", included: true },
          { text: "صفحات الرئيسية، من نحن، المميزات، الأسعار، الفريق، والتواصل", included: true },
          { text: "موقع عام بالعربية والإنجليزية", included: true },
          { text: "تبديل الوضع الفاتح والداكن", included: true },
          { text: "نماذج تواصل أساسية", included: true },
          { text: "إعدادات الموقع والرابط العام", included: true },
          { text: "لوحة الردود", included: true },
          { text: "بوابة الطلبات", included: false },
          { text: "مساحة تحليل البيانات", included: false },
          { text: "تقارير متقدمة", included: false },
        ],
      },
      {
        id: "operations",
        name: "Operations",
        badge: "نماذج + طلبات",
        price: "$29",
        recommended: true,
        cta: "ابدأ بخطة Operations",
        description:
          "للفرق التي تحتاج إلى جمع الطلبات، الحجوزات، الموافقات، التقارير، وردود العملاء.",
        bestFor:
          "شركات الخدمات، العيادات، الوكالات، المدارس، المنظمات، فرق التشغيل، وسير عمل الدعم.",
        workflow:
          "انشر الصفحات والنماذج، اجمع الردود، تابع الحالات، وأدر المتابعة.",
        includes: [
          "3 مواقع منشورة",
          "25 نموذج نشط",
          "5,000 رد شهري",
          "3 مستخدمين",
        ],
        features: [
          { text: "كل ميزات Presence", included: true },
          { text: "منشئ نماذج متقدم", included: true },
          { text: "نماذج الطلبات، الموافقات، الحجوزات، التقارير، والأوامر", included: true },
          { text: "البحث في الردود حسب الاسم أو البريد أو الحالة أو التاريخ أو القيم", included: true },
          { text: "إدارة حالة الردود", included: true },
          { text: "روابط نماذج عامة ومعاينات QR", included: true },
          { text: "تقارير أساسية", included: true },
          { text: "إعدادات الملف الشخصي والموقع", included: true },
          { text: "مساحة تحليل البيانات", included: false },
          { text: "تدفقات عمل متقدمة حسب الدور", included: false },
        ],
      },
      {
        id: "platform",
        name: "Platform",
        badge: "مساحة كاملة",
        price: "$79",
        recommended: false,
        cta: "ابدأ بخطة Platform",
        description:
          "للمؤسسات التي تريد مواقع، نماذج، ردود، تحليل بيانات، تقارير، أدوار، وتدفقات عمل مترابطة.",
        bestFor:
          "الشركات النامية، الأقسام، المنظمات، فرق الخدمات المتعددة، والمؤسسات ذات العمليات الرقمية المتعددة.",
        workflow:
          "ابنِ المواقع، اجمع البيانات، أدر الردود، حلل الملفات، أنشئ التقارير، وتحكم بصلاحيات الفريق.",
        includes: [
          "مواقع غير محدودة",
          "نماذج غير محدودة",
          "50,000 رد شهري",
          "مستخدمون غير محدودين",
        ],
        features: [
          { text: "كل ميزات Operations", included: true },
          { text: "رفع ملفات البيانات وفحص datasets", included: true },
          { text: "تقارير التحضير والجودة والإحصاءات والقيم الناقصة", included: true },
          { text: "إجراءات تنظيف وتحليل مساعد", included: true },
          { text: "تصويرات بيانية وإنشاء تقارير", included: true },
          { text: "قوالب CMS و ecommerce و HR/finance ومشاريع MEAL", included: true },
          { text: "صلاحيات متقدمة حسب الدور", included: true },
          { text: "نطاق مخصص ودعم بأولوية", included: true },
          { text: "لوحة إدارة ونشاط المنصة", included: true },
          { text: "تكاملات مخصصة", included: false },
        ],

        saving: "Saving...",
success: "Subscription request saved. Payment setup is not connected yet.",
loginRequired: "Please log in before choosing a plan.",
serverError: "Could not connect to server.",
      },
    ],

    customPlans: {
      label: "خطة مخصصة",
      title: "ابنِ خطة حول سير عملك الفعلي",
      subtitle:
        "اختر الوحدات التي يحتاجها فريقك. يتم تحديث التقدير مباشرة، وبعدها يمكن طلب خطة مناسبة.",
      summaryLabel: "باقتك المخصصة",
      summaryTitle: "الوحدات المختارة",
      summaryText:
        "هذا التقدير يعتمد على الوحدات المختارة. السعر النهائي يمكن أن يتغير حسب حدود الاستخدام، عدد الفريق، التكاملات، والدعم المطلوب.",
      estimatedPrice: "السعر الشهري التقديري",
      selectedModules: "الوحدات المختارة",
      noModules: "لم يتم اختيار أي وحدات بعد.",
      requestPlan: "طلب خطة مخصصة",
      note:
        "الخطط المخصصة مناسبة عندما يحتاج فريقك إلى حدود خاصة، تدفقات عمل، تكاملات، أو صلاحيات إدارية.",
      modules: [
        {
          id: "website",
          name: "منشئ المواقع",
          price: "$15",
          priceValue: 15,
          defaultSelected: true,
          description:
            "أنشئ وانشر مواقع بعلامتك التجارية، صفحات هبوط، صفحات خدمات، وبوابات عامة.",
          value:
            "مناسب للحضور العام، صفحات الخدمات، صفحات التسويق، والمواقع المنشورة.",
        },
        {
          id: "forms",
          name: "النماذج والردود",
          price: "$19",
          priceValue: 19,
          defaultSelected: true,
          description:
            "ابنِ النماذج، اجمع الردود، عاين النماذج، ابحث في الردود، وحدّث الحالات.",
          value:
            "مناسب للتواصل، الطلبات، الحجوزات، الموافقات، التقارير، الأوامر، والاختبارات.",
        },
        {
          id: "requests",
          name: "بوابة الطلبات",
          price: "$19",
          priceValue: 19,
          defaultSelected: false,
          description:
            "حوّل الردود إلى طلبات قابلة للمتابعة مع الحالات، الأولويات، المراجعة، والمتابعة.",
          value:
            "مناسب لفرق التشغيل التي تحتاج إلى إدارة طلبات العملاء أو الطلبات الداخلية.",
        },
        {
          id: "data",
          name: "مساحة تحليل البيانات",
          price: "$39",
          priceValue: 39,
          defaultSelected: false,
          description:
            "ارفع الملفات، افحص البيانات، أنشئ تقارير جودة، نظف البيانات، وشغّل التحليل.",
          value:
            "مناسب للفرق التي تعمل مع الجداول، البيانات الميدانية، التقارير، ومؤشرات الأداء.",
        },
        {
          id: "reports",
          name: "مركز التقارير",
          price: "$29",
          priceValue: 29,
          defaultSelected: false,
          description:
            "أنشئ تقارير، رسوم بيانية، ملخصات مشاريع، تقارير تشغيل، وصفحات أداء.",
          value:
            "مناسب للفرق التي تحتاج إلى عرض النتائج للإدارة أو العملاء أو الشركاء أو الممولين.",
        },
        {
          id: "commerce",
          name: "الطلبات والحجوزات",
          price: "$24",
          priceValue: 24,
          defaultSelected: false,
          description:
            "استقبل الطلبات، الحجوزات، طلبات الخدمة، الاستشارات، والمواعيد.",
          value:
            "مناسب لشركات الخدمات التي تريد من العملاء الحجز أو إرسال الطلبات عبر الإنترنت.",
        },
        {
          id: "cms",
          name: "CMS والمحتوى",
          price: "$29",
          priceValue: 29,
          defaultSelected: false,
          description:
            "أدر مجموعات محتوى قابلة لإعادة الاستخدام مثل الخدمات، المشاريع، المقالات، الموارد، والأدلة.",
          value:
            "مناسب للمواقع الكبيرة التي تحتاج إلى محتوى منظم ويتم تحديثه باستمرار.",
        },
        {
          id: "workflows",
          name: "تدفقات العمل المتقدمة",
          price: "$49",
          priceValue: 49,
          defaultSelected: false,
          description:
            "أنشئ تدفقات عمل داخلية للموافقات، الموارد البشرية، المالية، مشاريع MEAL، الأدوار، والصلاحيات.",
          value:
            "مناسب للمؤسسات التي لديها عمليات متعددة الخطوات وصلاحيات فريق حسب الدور.",

          saving: "جارٍ الحفظ...",
success: "تم حفظ طلب الاشتراك. إعداد الدفع غير متصل بعد.",
loginRequired: "يرجى تسجيل الدخول قبل اختيار خطة.",
serverError: "تعذر الاتصال بالخادم.",
        },
      ],
    },
  },
};

export const getPricingContent = (lang = "en") =>
  pricingContent[lang === "ar" ? "ar" : "en"];