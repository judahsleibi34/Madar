export const adminDashboardContent = {
  en: {
    eyebrow: "Admin overview",
    title: "Dashboard",
    subtitle:
      "Monitor platform activity, active projects, revenue, system health, and resource usage.",
    liveStatus: "Live",
    lastUpdated: "Updated just now",
    platformHealth: "Platform healthy",
    chartScope: "Revenue, Jan-Aug",
    heroTitle: "Admin monitoring center",
    heroSubtitle:
      "Track users, revenue, services, and infrastructure health from one operational view.",
    viewReports: "View reports",
    todayOrders: "12 new workspace events",
    todayRevenue: "$4.2K revenue today",

    runningProjects: "Running Projects",
    users: "Users",
    totalRevenue: "Total Revenue",
    uptime: "Uptime",

    projectsSub: "+8 this month",
    usersSub: "+124 new users",
    revenueSub: "+18.4% growth",
    uptimeSub: "Last 30 days",

    serverInfo: "Server Info",
    serverSubtitle: "Core platform services status",
    serverStatus: "Status",
    healthy: "Healthy",
    activeServices: "Active Services",
    serverRegion: "Region",
    regionValue: "Middle East",

    usage: "Usage",
    usageSubtitle: "Current infrastructure usage",
    cpu: "CPU",
    memory: "Memory",
    storage: "Storage",
    network: "Network",

    cashFlow: "Cash Through Time",
    cashSubtitle: "Monthly revenue performance",
    userSignals: "User Signals",
    userSignalsSubtitle: "Live account and traffic indicators",
    activeUsers: "Active users",
    sessions: "Sessions",
    signups: "New signups",
    conversion: "Conversion",
    serviceHealth: "Service Health",
    serviceHealthSubtitle: "Request quality and infrastructure pressure",
    apiLatency: "API latency",
    errorRate: "Error rate",
    queueDepth: "Queue depth",
    databaseLoad: "Database load",

    months: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"],
  },

  ar: {
    eyebrow: "نظرة عامة للمسؤول",
    title: "لوحة التحكم",
    subtitle:
      "راقب نشاط المنصة والمشاريع النشطة والإيرادات وصحة النظام واستخدام الموارد.",
    liveStatus: "مباشر",
    lastUpdated: "تم التحديث الآن",
    platformHealth: "المنصة مستقرة",
    chartScope: "الإيرادات، يناير-أغسطس",
    heroTitle: "مركز مراقبة الإدارة",
    heroSubtitle:
      "تابع المستخدمين، والإيرادات، والخدمات، وصحة البنية التحتية من واجهة تشغيلية واحدة.",
    viewReports: "عرض التقارير",
    todayOrders: "12 حدثاً جديداً في مساحة العمل",
    todayRevenue: "إيرادات اليوم $4.2K",

    runningProjects: "المشاريع النشطة",
    users: "المستخدمون",
    totalRevenue: "إجمالي الإيرادات",
    uptime: "وقت التشغيل",

    projectsSub: "+8 هذا الشهر",
    usersSub: "+124 مستخدمًا جديدًا",
    revenueSub: "+18.4% نمو",
    uptimeSub: "آخر 30 يومًا",

    serverInfo: "معلومات الخادم",
    serverSubtitle: "حالة خدمات المنصة الأساسية",
    serverStatus: "الحالة",
    healthy: "مستقر",
    activeServices: "الخدمات النشطة",
    serverRegion: "المنطقة",
    regionValue: "الشرق الأوسط",

    usage: "الاستخدام",
    usageSubtitle: "الاستخدام الحالي للبنية التحتية",
    cpu: "المعالج",
    memory: "الذاكرة",
    storage: "التخزين",
    network: "الشبكة",

    cashFlow: "التدفق المالي عبر الزمن",
    cashSubtitle: "أداء الإيرادات الشهرية",
    userSignals: "مؤشرات المستخدمين",
    userSignalsSubtitle: "مؤشرات الحسابات والزيارات المباشرة",
    activeUsers: "المستخدمون النشطون",
    sessions: "الجلسات",
    signups: "تسجيلات جديدة",
    conversion: "التحويل",
    serviceHealth: "صحة الخدمات",
    serviceHealthSubtitle: "جودة الطلبات وضغط البنية التحتية",
    apiLatency: "زمن استجابة API",
    errorRate: "معدل الأخطاء",
    queueDepth: "عمق قائمة الانتظار",
    databaseLoad: "حمل قاعدة البيانات",

    months: ["ينا", "فبر", "مار", "أبر", "ماي", "يون", "يول", "أغس"],
  },
};

export const getAdminDashboardContent = (lang = "en") =>
  adminDashboardContent[lang === "ar" ? "ar" : "en"];
