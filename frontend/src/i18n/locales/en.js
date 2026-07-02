const en = {
  common: {
    save: "Save",
    cancel: "Cancel",
    close: "Close",
    back: "Back",
    settings: "Settings",
    upgrade: "Upgrade",
    manage: "Manage",
    viewAll: "View all",
    markAllRead: "Mark all read",
    read: "Read",
    unread: "Unread",
    enabled: "Enabled",
    locked: "Locked",
    included: "Included",
    active: "Active",
    loading: "Loading...",
  },
  language: {
    en: "English",
    ar: "Arabic",
    switchTo: "Switch language to {{language}}",
  },
  sidebar: {
    brand: "Madar",
    subtitle: "Admin Panel",
    userSubtitle: "{{name}} workspace",
    aria: "Dashboard sidebar",
    navigation: "Dashboard navigation",
    home: "Home",
    dashboard: "Dashboard",
    pageBuilder: "Page Builder",
    submissions: "Submissions",
    dataLogs: "Data Logs",
    myPlan: "My Plan",
    settings: "Settings",
    languageSwitch: "Arabic",
    logout: "Log out",
    themeMode: "Theme",
    userManagement: "User Management",
    accountAccess: "Account access",
    admin: "Admin",
    userRole: "User",
    security: "Security",
    search: "Search...",
  },
  notifications: {
    title: "Notifications",
    kicker: "Workspace",
    subtitle: "Review recent workspace, builder, and account activity.",
    ariaRecent: "Recent notifications",
    summary: "Notification summary",
    total: "Total",
    unread: "Unread",
    read: "Read",
    sources: "Sources",
    items: "{{count}} items",
    unreadCount: "{{count}} unread",
    viewAll: "View all notifications",
    groups: {
      today: "Today",
      yesterday: "Yesterday",
      earlier: "Earlier",
    },
    sourcesList: {
      forms: "Forms",
      builder: "Builder",
      system: "System",
      billing: "Billing",
      data: "Data",
    },
    dummy: {
      newResponse: {
        title: "New form response",
        detail: "A visitor submitted a connected form.",
        time: "9 min ago",
      },
      sitePublished: {
        title: "Website updated",
        detail: "Your latest builder changes are ready to review.",
        time: "1 hour ago",
      },
      workspaceHealth: {
        title: "Workspace health",
        detail: "All active tools are running normally.",
        time: "Today",
      },
      planReminder: {
        title: "Plan usage reviewed",
        detail: "Your workspace usage report is ready in My Plan.",
        time: "Yesterday",
      },
      dataImport: {
        title: "Data import complete",
        detail: "The latest CSV upload finished processing.",
        time: "Yesterday",
      },
    },
  },
  myPlan: {
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
    enabledModule: "Available module",
    lockedModule: "Upgrade module",
    modulePrice: "Module price",
    openModule: "Open module",
    unlockModule: "Unlock module",
    plans: {
      fullPlatform: "Full platform",
      builder: "{{builder}} builder",
    },
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
};

export default en;
