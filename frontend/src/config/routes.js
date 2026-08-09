export const PUBLIC_ROUTES = {
  home: "/",
  pricing: "/pricing",
  pricingBasePlans: "/pricing/base-plans",
  pricingCustomPlan: "/pricing/custom-plan",
  team: "/team",
  about: "/about",
  contact: "/contact",
  privacyPolicy: "/privacy-policy",
  termsAndConditions: "/terms-and-conditions",
  demo: "/demo",
  login: "/login",
  signup: "/signup",
  verifyEmail: "/verify-email",
};

export const DASHBOARD_ROUTES = {
  dashboard: "/dashboard",
  pageBuilder: "/page-builder",
  builderResponses: "/builder-responses",
  builderData: "/builder-data",
  calendar: "/calendar",
  archive: "/archive",
  ecommerce: "/ecommerce",
  ecommerceTags: "/ecommerce/tags",
  ecommerceCategories: "/ecommerce/categories",
  ecommerceProducts: "/ecommerce/products",
  ecommerceCvRerank: "/ecommerce/cv-rerank",
  ecommerceStore: "/ecommerce/store",
  notifications: "/notifications",
  myPlan: "/my-plan",
  settings: "/settings",
  settingsSecurity: "/settings/security",
  adminUsers: "/admin/users",
  adminAccountAccess: "/admin/account-access",
};

export const POST_LOGIN_FALLBACK_ROUTE = DASHBOARD_ROUTES.dashboard;
